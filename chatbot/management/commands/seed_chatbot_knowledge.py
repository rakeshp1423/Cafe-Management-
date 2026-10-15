from django.core.management.base import BaseCommand

from chatbot.models import KnowledgeDocument


STARTER_DOCUMENTS = (
    {
        'source_type': 'faq',
        'source_identifier': 'starter-menu-ingredients',
        'title': 'Menu descriptions and ingredient questions',
        'content': (
            'The assistant can answer ingredient questions only when ingredients are '
            'explicitly named in the current menu description or another approved café '
            'knowledge document. Menu descriptions may be incomplete and are not full '
            'recipes or allergen guarantees. The café has not provided a verified '
            'complete ingredient or allergen list in the starter knowledge. For allergy '
            'or strict dietary questions, customers should contact the café directly '
            'before ordering. Add verified dish ingredients and allergen information '
            'to this document or the relevant menu description through Django admin.'
        ),
    },
    {
        'source_type': 'cafe_info',
        'source_identifier': 'starter-cafe-story',
        'title': 'About the café',
        'content': (
            'The café website describes its goal as creating a warm, inviting place '
            'for coffee and good company. Its story says it values ethically sourced '
            'coffee beans, locally sourced ingredients, community, and craft. The '
            'website describes its specials as seasonal. This is general story text, '
            'not a live ingredient, menu availability, or supplier guarantee.'
        ),
    },
)


class Command(BaseCommand):
    help = 'Create editable starter café knowledge documents without adding fake menu data.'

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0
        for values in STARTER_DOCUMENTS:
            _document, created = KnowledgeDocument.objects.get_or_create(
                source_type=values['source_type'],
                source_identifier=values['source_identifier'],
                defaults={
                    'title': values['title'],
                    'content': values['content'],
                    'active': True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"Created starter FAQ: {values['title']}")
            else:
                existing_count += 1
                self.stdout.write(f"Kept existing document: {values['title']}")

        self.stdout.write(self.style.SUCCESS(
            f'Created {created_count} starter documents; preserved {existing_count} '
            'existing documents. Review or edit them in Django admin, then run '
            'ingest_chatbot_knowledge.'
        ))
