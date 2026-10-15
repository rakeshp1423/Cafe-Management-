from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from chatbot.models import ChatConversation


class Command(BaseCommand):
    help = 'Delete chatbot conversations older than the configured retention period.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(
            days=settings.CHATBOT_CONVERSATION_RETENTION_DAYS
        )
        deleted, _ = ChatConversation.objects.filter(updated_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(
            f'Deleted {deleted} expired chatbot database records.'
        ))
