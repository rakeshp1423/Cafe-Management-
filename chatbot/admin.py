from django.contrib import admin

from .models import ChatConversation, ChatMessage, ChatTurn, DocumentChunk, KnowledgeDocument


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_type', 'source_identifier', 'active', 'updated_at')
    list_filter = ('source_type', 'active')
    search_fields = ('title', 'content', 'source_identifier')
    readonly_fields = ('content_hash', 'created_at', 'updated_at')


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'chunk_index', 'created_at')
    list_select_related = ('document',)
    search_fields = ('document__title', 'text')
    readonly_fields = ('document', 'chunk_index', 'text', 'content_hash', 'created_at')


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    readonly_fields = ('id', 'user', 'created_at', 'updated_at')
    exclude = ('session_key',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    readonly_fields = ('conversation', 'role', 'content', 'sources', 'created_at')


@admin.register(ChatTurn)
class ChatTurnAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'conversation', 'created_at')
    readonly_fields = ('request_id', 'conversation', 'question', 'answer', 'sources', 'created_at')
