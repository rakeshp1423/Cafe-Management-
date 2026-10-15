import uuid
from io import StringIO
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from chatbot.models import (
    ChatConversation,
    ChatMessage,
    ChatTurn,
    DocumentChunk,
    KnowledgeDocument,
)
from chatbot.services.providers import ProviderError, embed_text
from chatbot.management.commands.ingest_chatbot_knowledge import split_text
from core.models import MenuItem


def vector(first=1.0, second=0.0):
    return [first, second] + [0.0] * 382


class KnowledgeIngestionTests(TestCase):
    def test_chunker_splits_long_text_with_overlap(self):
        words = [f'word{index:03d}' for index in range(100)]
        chunks = split_text(' '.join(words), chunk_size=100, overlap=20)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))
        for previous, current in zip(chunks, chunks[1:]):
            self.assertIn(previous.split()[-1], current.split())

    def test_ingestion_is_idempotent_and_reindexes_changed_menu_content(self):
        item = MenuItem.objects.create(
            name='Cappuccino',
            description='Espresso with steamed milk',
            price='150.00',
        )
        with patch(
            'chatbot.management.commands.ingest_chatbot_knowledge.embed_text',
            return_value=vector(),
        ) as embedding:
            call_command('ingest_chatbot_knowledge', stdout=StringIO())
            call_command('ingest_chatbot_knowledge', stdout=StringIO())
            self.assertEqual(embedding.call_count, 1)
            self.assertEqual(DocumentChunk.objects.count(), 1)

            item.description = 'Espresso with oat milk'
            item.save()
            call_command('ingest_chatbot_knowledge', stdout=StringIO())
            self.assertEqual(embedding.call_count, 2)
            self.assertIn('oat milk', DocumentChunk.objects.get().text)

        item.delete()
        call_command('ingest_chatbot_knowledge', stdout=StringIO())
        self.assertFalse(KnowledgeDocument.objects.filter(source_type='menu').exists())
        self.assertFalse(DocumentChunk.objects.exists())

    def test_ingestion_preserves_existing_data_when_embedding_fails(self):
        item = MenuItem.objects.create(
            name='Tea',
            description='Black tea',
            price='60.00',
        )
        with patch(
            'chatbot.management.commands.ingest_chatbot_knowledge.embed_text',
            return_value=vector(),
        ):
            call_command('ingest_chatbot_knowledge', stdout=StringIO())
        chunk = DocumentChunk.objects.get()

        item.description = 'Green tea'
        item.save()
        with patch(
            'chatbot.management.commands.ingest_chatbot_knowledge.embed_text',
            side_effect=ProviderError('embedding failed'),
        ):
            with self.assertRaises(CommandError):
                call_command('ingest_chatbot_knowledge', stdout=StringIO())

        chunk.refresh_from_db()
        self.assertIn('Black tea', chunk.text)

    def test_ingestion_removes_chunks_from_inactive_manual_documents(self):
        document = KnowledgeDocument.objects.create(
            title='Reservation policy',
            source_type='policy',
            source_identifier='reservation',
            content='Call us to reserve.',
        )
        with patch(
            'chatbot.management.commands.ingest_chatbot_knowledge.embed_text',
            return_value=vector(),
        ):
            call_command('ingest_chatbot_knowledge', stdout=StringIO())
        self.assertTrue(document.chunks.exists())

        document.active = False
        document.save()
        call_command('ingest_chatbot_knowledge', stdout=StringIO())

        self.assertFalse(document.chunks.exists())

    def test_retention_command_deletes_expired_conversations(self):
        conversation = ChatConversation.objects.create(session_key='anonymous-session')
        ChatMessage.objects.create(
            conversation=conversation,
            role='user',
            content='A past question',
        )
        ChatConversation.objects.filter(pk=conversation.pk).update(
            updated_at=timezone.now() - timedelta(days=31)
        )

        call_command('purge_chatbot_conversations', stdout=StringIO())

        self.assertFalse(ChatConversation.objects.filter(pk=conversation.pk).exists())
        self.assertFalse(ChatMessage.objects.exists())

    def test_seed_command_creates_editable_knowledge_without_menu_items(self):
        call_command('seed_chatbot_knowledge', stdout=StringIO())

        self.assertEqual(KnowledgeDocument.objects.count(), 2)
        self.assertFalse(MenuItem.objects.exists())
        ingredients = KnowledgeDocument.objects.get(
            source_identifier='starter-menu-ingredients'
        )
        self.assertIn('not full recipes or allergen guarantees', ingredients.content)

        ingredients.content = 'Verified café-specific information.'
        ingredients.save()
        call_command('seed_chatbot_knowledge', stdout=StringIO())

        ingredients.refresh_from_db()
        self.assertEqual(ingredients.content, 'Verified café-specific information.')
        self.assertEqual(KnowledgeDocument.objects.count(), 2)


class RetrievalTests(TestCase):
    def setUp(self):
        self.document = KnowledgeDocument.objects.create(
            title='Coffee',
            source_type='faq',
            source_identifier='coffee',
            content='Coffee details',
        )

    def create_chunk(self, document, index, embedding):
        return DocumentChunk.objects.create(
            document=document,
            chunk_index=index,
            text=f'Chunk {index}',
            content_hash=f'hash-{index}',
            embedding=embedding,
        )

    @patch('chatbot.services.retrieval.embed_text', return_value=vector())
    def test_retrieves_relevant_chunks_and_excludes_inactive_documents(self, _embed):
        relevant = self.create_chunk(self.document, 0, vector())
        self.create_chunk(self.document, 1, vector(0.0, 1.0))
        inactive = KnowledgeDocument.objects.create(
            title='Inactive',
            source_type='faq',
            source_identifier='inactive',
            content='inactive',
            active=False,
        )
        self.create_chunk(inactive, 0, vector())

        with override_settings(CHATBOT_MAX_COSINE_DISTANCE=0.2):
            from chatbot.services.retrieval import retrieve_chunks

            results = retrieve_chunks('coffee')

        self.assertEqual([chunk.pk for chunk in results], [relevant.pk])

    @patch('chatbot.services.retrieval.embed_text', return_value=vector())
    def test_irrelevant_query_has_no_chunks(self, _embed):
        self.create_chunk(self.document, 0, vector(0.0, 1.0))
        with override_settings(CHATBOT_MAX_COSINE_DISTANCE=0.1):
            from chatbot.services.retrieval import retrieve_chunks

            self.assertEqual(retrieve_chunks('unrelated question'), [])

    @override_settings(CHATBOT_EMBEDDING_PROVIDER='ollama')
    @patch('chatbot.services.providers._post_json', return_value={'embeddings': [[0.1]]})
    def test_invalid_embedding_dimensions_are_rejected(self, _post):
        with self.assertRaises(ProviderError):
            embed_text('test')


class ChatApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/chatbot/chat/'
        MenuItem.objects.create(
            name='Flat white',
            description='Espresso and milk',
            price='180.00',
        )
        MenuItem.objects.create(
            name='Mocha',
            description='Coffee and chocolate',
            price='220.00',
        )

    def test_budget_query_uses_live_prices_and_returns_schema(self):
        response = self.client.post(
            self.url,
            {'message': 'Which items cost less than ₹200?', 'request_id': str(uuid.uuid4())},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {'answer', 'conversation_id', 'sources'},
        )
        self.assertIn('Flat white: ₹180.00', response.json()['answer'])
        self.assertNotIn('Mocha', response.json()['answer'])
        self.assertEqual(response.json()['sources'][0]['source_type'], 'menu')
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.assertEqual(ChatTurn.objects.count(), 1)

    def test_duplicate_request_id_does_not_duplicate_messages(self):
        request_id = str(uuid.uuid4())
        payload = {
            'message': 'Which items cost less than ₹200?',
            'request_id': request_id,
        }
        first = self.client.post(self.url, payload, format='json')
        second = self.client.post(self.url, payload, format='json')

        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.assertEqual(ChatTurn.objects.count(), 1)

    def test_blank_oversized_and_invalid_messages_are_rejected(self):
        self.assertEqual(
            self.client.post(self.url, {'message': '   '}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(self.url, {'message': 'x' * 1001}, format='json').status_code,
            400,
        )
        self.assertEqual(
            self.client.post(self.url, {'message': 'hello', 'conversation_id': 'bad'},
                             format='json').status_code,
            400,
        )

    def test_owner_cannot_access_another_users_conversation(self):
        owner = User.objects.create_user(username='owner', password='password')
        other = User.objects.create_user(username='other', password='password')
        conversation = ChatConversation.objects.create(user=owner)
        self.client.force_authenticate(user=other)

        response = self.client.post(
            self.url,
            {
                'message': 'hello',
                'conversation_id': str(conversation.id),
                'request_id': str(uuid.uuid4()),
            },
            format='json',
        )

        self.assertEqual(response.status_code, 404)

    def test_provider_failure_returns_safe_service_error(self):
        with patch(
            'chatbot.services.chat.retrieve_chunks',
            side_effect=ProviderError('private provider detail'),
        ):
            response = self.client.post(
                self.url,
                {'message': 'Tell me something about the menu'},
                format='json',
            )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private provider detail', response.content.decode())
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_unverified_menu_classifications_are_not_invented(self):
        response = self.client.post(
            self.url,
            {'message': 'What vegetarian dishes do you have?'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('does not store verified', response.json()['answer'])

    def test_exact_item_price_uses_current_menu_data(self):
        response = self.client.post(
            self.url,
            {'message': 'What is the price of Flat white?'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Flat white: ₹180.00', response.json()['answer'])
        self.assertEqual(response.json()['sources'][0]['source_type'], 'menu')

    def test_unknown_question_returns_fallback_without_claimed_sources(self):
        response = self.client.post(
            self.url,
            {'message': 'What is the café Wi-Fi password?'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("couldn't find that", response.json()['answer'])
        self.assertEqual(response.json()['sources'], [])

    def test_reservation_answer_does_not_claim_booking_or_availability(self):
        response = self.client.post(
            self.url,
            {'message': 'How can I reserve a table?'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        answer = response.json()['answer']
        self.assertIn('Book a Table', answer)
        self.assertIn('1-8 guests', answer)
        self.assertIn('date and time', answer)
        self.assertIn('does not check availability', answer)
        self.assertIn('automatically confirm bookings', answer)

    def test_user_can_delete_their_own_conversation(self):
        user = User.objects.create_user(username='owner', password='password')
        conversation = ChatConversation.objects.create(user=user)
        ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content='Hello',
        )
        self.client.force_authenticate(user=user)

        response = self.client.delete(
            f'/api/chatbot/conversations/{conversation.id}/'
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ChatConversation.objects.filter(pk=conversation.pk).exists())

    def test_chatbot_endpoint_is_rate_limited(self):
        cache.clear()
        self.addCleanup(cache.clear)
        responses = [
            self.client.post(
                self.url,
                {
                    'message': 'Which items cost less than ₹200?',
                    'request_id': str(uuid.uuid4()),
                },
                format='json',
            )
            for _ in range(10)
        ]
        limited = self.client.post(
            self.url,
            {'message': 'Which items cost less than ₹200?', 'request_id': str(uuid.uuid4())},
            format='json',
        )

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(limited.status_code, 429)

    def test_site_widget_supplies_a_csrf_token_for_chat(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        page = csrf_client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('TheMenu AI', page.content.decode())

        denied = csrf_client.post(
            self.url,
            {'message': 'Which items cost less than ₹200?'},
            format='json',
        )
        self.assertEqual(denied.status_code, 403)

        token = csrf_client.cookies['csrftoken'].value
        allowed = csrf_client.post(
            self.url,
            {'message': 'Which items cost less than ₹200?'},
            format='json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(allowed.status_code, 200)
