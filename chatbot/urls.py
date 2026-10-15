from django.urls import path

from .views import ChatView, ConversationView


urlpatterns = [
    path('chat/', ChatView.as_view(), name='chatbot-chat'),
    path(
        'conversations/<uuid:conversation_id>/',
        ConversationView.as_view(),
        name='chatbot-conversation',
    ),
]
