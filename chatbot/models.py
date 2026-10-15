import json
import math
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class EmbeddingField(models.Field):
    description = 'A fixed-dimension vector (pgvector in PostgreSQL, JSON text in SQLite)'

    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return f'vector({settings.CHATBOT_EMBEDDING_DIMENSIONS})'
        return 'text'

    def get_internal_type(self):
        return 'TextField'

    def to_python(self, value):
        if value is None:
            return None
        if hasattr(value, 'tolist'):
            value = value.tolist()
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError) as exc:
                raise ValueError('Stored embedding is not valid vector data.') from exc
        if not isinstance(value, (list, tuple)):
            raise ValueError('Embedding must be a list of numeric values.')
        vector = [float(component) for component in value]
        if len(vector) != settings.CHATBOT_EMBEDDING_DIMENSIONS:
            raise ValueError('Embedding dimension does not match the configured model.')
        if not all(math.isfinite(component) for component in vector):
            raise ValueError('Embedding values must be finite numbers.')
        return vector

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def get_prep_value(self, value):
        vector = self.to_python(value)
        if vector is None:
            return None
        return json.dumps(vector, allow_nan=False, separators=(',', ':'))

    def get_placeholder(self, value, compiler, connection):
        if connection.vendor == 'postgresql':
            return '%s::vector'
        return '%s'


class KnowledgeDocument(models.Model):
    SOURCE_TYPES = [
        ('menu', 'Menu'),
        ('cafe_info', 'Café information'),
        ('faq', 'FAQ'),
        ('policy', 'Policy'),
        ('service', 'Service information'),
    ]

    title = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_identifier = models.CharField(max_length=120)
    content = models.TextField()
    content_hash = models.CharField(max_length=64, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('source_type', 'source_identifier'),
                name='chatbot_unique_knowledge_source',
            )
        ]
        indexes = [
            models.Index(fields=('active', 'source_type'), name='chatbot_doc_active_type')
        ]
        ordering = ('source_type', 'title')

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        KnowledgeDocument, on_delete=models.CASCADE, related_name='chunks'
    )
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    content_hash = models.CharField(max_length=64)
    embedding = EmbeddingField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('document', 'chunk_index'),
                name='chatbot_unique_document_chunk',
            )
        ]
        indexes = [
            models.Index(fields=('document', 'chunk_index'), name='chatbot_chunk_doc_idx')
        ]

    def __str__(self):
        return f'{self.document.title} — {self.chunk_index}'


class ChatConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chatbot_conversations',
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(user__isnull=False, session_key__isnull=True)
                    | Q(user__isnull=True, session_key__isnull=False)
                ),
                name='chatbot_conversation_one_owner',
            )
        ]
        indexes = [
            models.Index(fields=('user', 'updated_at'), name='chatbot_user_updated_idx')
        ]


class ChatMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]

    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=('conversation', 'created_at'), name='chatbot_message_order_idx'
            )
        ]
        ordering = ('created_at', 'pk')


class ChatTurn(models.Model):
    request_id = models.UUIDField(unique=True, editable=False)
    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name='turns'
    )
    question = models.TextField()
    answer = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=('conversation', 'created_at'), name='chatbot_turn_order_idx')]
