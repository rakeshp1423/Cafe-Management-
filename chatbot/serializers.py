from django.conf import settings
from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=settings.CHATBOT_MAX_MESSAGE_LENGTH,
        trim_whitespace=True,
        allow_blank=False,
    )
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    request_id = serializers.UUIDField(required=False)
