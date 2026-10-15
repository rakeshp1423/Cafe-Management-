from rest_framework.throttling import ScopedRateThrottle


class ChatbotRateThrottle(ScopedRateThrottle):
    scope = 'chatbot'
