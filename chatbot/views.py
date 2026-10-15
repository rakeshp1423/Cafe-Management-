import logging
import uuid

from django.db import DatabaseError, IntegrityError, transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from chatbot.serializers import ChatRequestSerializer
from chatbot.services.chat import (
    answer_question,
    get_existing_turn,
    get_owned_conversation,
    save_turn,
)
from chatbot.services.providers import ProviderError
from chatbot.throttles import ChatbotRateThrottle


logger = logging.getLogger(__name__)


@method_decorator(csrf_protect, name='dispatch')
class ChatView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ChatbotRateThrottle]
    throttle_scope = 'chatbot'

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Please enter a message of up to '
                 f'{serializer.fields["message"].max_length} characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = serializer.validated_data['message']
        conversation_id = serializer.validated_data.get('conversation_id')
        request_id = serializer.validated_data.get('request_id') or uuid.uuid4()
        previous_turn = get_existing_turn(request, request_id)
        if previous_turn:
            return Response({
                'answer': previous_turn.answer,
                'conversation_id': str(previous_turn.conversation_id),
                'sources': previous_turn.sources,
            })

        conversation = None
        if conversation_id:
            conversation = get_owned_conversation(request, conversation_id)
            if conversation is None:
                return Response(
                    {'error': 'Conversation not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            result = answer_question(request, question, conversation)
            with transaction.atomic():
                conversation = save_turn(
                    request,
                    question,
                    result['answer'],
                    result['sources'],
                    conversation,
                    request_id,
                )
        except IntegrityError:
            previous_turn = get_existing_turn(request, request_id)
            if previous_turn:
                return Response({
                    'answer': previous_turn.answer,
                    'conversation_id': str(previous_turn.conversation_id),
                    'sources': previous_turn.sources,
                })
            logger.exception('Chatbot request could not be committed.')
            return Response(
                {'error': 'The assistant could not save this conversation. Please retry.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ProviderError as exc:
            logger.warning('Chatbot provider failure (%s).', type(exc).__name__)
            return Response(
                {'error': 'The assistant is temporarily unavailable. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DatabaseError:
            logger.exception('Chatbot database operation failed.')
            return Response(
                {'error': 'The assistant could not save this conversation. Please retry.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            'answer': result['answer'],
            'conversation_id': str(conversation.id),
            'sources': result['sources'],
        })


@method_decorator(csrf_protect, name='dispatch')
class ConversationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ChatbotRateThrottle]
    throttle_scope = 'chatbot'

    def delete(self, request, conversation_id):
        conversation = get_owned_conversation(request, conversation_id)
        if conversation is None:
            return Response(
                {'error': 'Conversation not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
