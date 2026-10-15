import hashlib
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import MenuItem
from chatbot.models import DocumentChunk, KnowledgeDocument
from chatbot.services.providers import ProviderError, embed_text


def normalize_text(text):
    return '\n'.join(
        re.sub(r'\s+', ' ', line).strip()
        for line in text.splitlines()
        if line.strip()
    )


def content_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def split_text(text, chunk_size=900, overlap=120):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start
        length = 0
        while end < len(words):
            added_length = len(words[end]) + (1 if end > start else 0)
            if end > start and length + added_length > chunk_size:
                break
            length += added_length
            end += 1
        chunks.append(' '.join(words[start:end]))
        if end == len(words):
            break
        next_start = end
        overlap_length = 0
        while next_start > start and overlap_length < overlap:
            next_start -= 1
            overlap_length += len(words[next_start]) + 1
        start = max(next_start, start + 1)
    return chunks


class Command(BaseCommand):
    help = 'Index approved menu and café documents for TheMenu AI.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show sources and chunks that would be indexed without changing data.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        sources = []
        for item in MenuItem.objects.all().order_by('pk'):
            content = normalize_text(
                f'Menu item: {item.name}\nDescription: {item.description}'
            )
            sources.append(('menu', str(item.pk), item.name, content))

        sources.extend(
            (
                document.source_type,
                document.source_identifier,
                document.title,
                normalize_text(document.content),
            )
            for document in KnowledgeDocument.objects.exclude(source_type='menu')
            if document.active and document.content.strip()
        )
        source_keys = {(source_type, identifier) for source_type, identifier, *_ in sources}
        menu_ids = [identifier for kind, identifier in source_keys if kind == 'menu']
        obsolete = KnowledgeDocument.objects.filter(source_type='menu').exclude(
            source_identifier__in=menu_ids
        )
        inactive_manual = KnowledgeDocument.objects.exclude(source_type='menu').filter(
            active=False
        )

        if dry_run:
            self.stdout.write(
                f'{len(sources)} active sources; '
                f'{sum(len(split_text(content)) for *_, content in sources)} chunks; '
                f'{obsolete.count()} obsolete menu sources would be removed; '
                f'{DocumentChunk.objects.filter(document__in=inactive_manual).count()} '
                'chunks from inactive documents would be removed.'
            )
            return

        try:
            for source_type, identifier, title, content in sources:
                self.stdout.write(f'Indexing {title[:200]}')
                self._ingest_source(source_type, identifier, title, content)
        except ProviderError as exc:
            raise CommandError(
                f'Embedding failed: {exc}. The failed source was left unchanged; '
                'earlier sources in this run may already have been updated.'
            ) from exc

        obsolete.delete()
        DocumentChunk.objects.filter(document__in=inactive_manual).delete()
        self.stdout.write(self.style.SUCCESS(f'Indexed {len(sources)} approved sources.'))

    def _ingest_source(self, source_type, identifier, title, content):
        pieces = split_text(content)
        document = KnowledgeDocument.objects.filter(
            source_type=source_type,
            source_identifier=identifier,
        ).first()
        old_chunks = {
            chunk.chunk_index: chunk
            for chunk in document.chunks.all()
        } if document else {}

        chunk_data = [
            (index, text, content_hash(text))
            for index, text in enumerate(pieces)
        ]
        if (
            document
            and document.active
            and document.title == title[:200]
            and document.content_hash == content_hash(content)
            and len(old_chunks) == len(chunk_data)
            and all(
                index in old_chunks
                and old_chunks[index].content_hash == digest
                and old_chunks[index].embedding is not None
                for index, _text, digest in chunk_data
            )
        ):
            return

        prepared = []
        for index, text, digest in chunk_data:
            current = old_chunks.get(index)
            vector = current.embedding if current and current.content_hash == digest else None
            if vector is None:
                vector = embed_text(text)
            prepared.append((index, text, digest, vector))

        with transaction.atomic():
            if document is None:
                document = KnowledgeDocument(
                    source_type=source_type,
                    source_identifier=identifier,
                )
            document.title = title[:200]
            document.content = content
            document.content_hash = content_hash(content)
            document.active = True
            document.save()
            keep_ids = []
            for index, text, digest, vector in prepared:
                chunk, _ = DocumentChunk.objects.update_or_create(
                    document=document,
                    chunk_index=index,
                    defaults={
                        'text': text,
                        'content_hash': digest,
                        'embedding': vector,
                    },
                )
                keep_ids.append(chunk.pk)
            document.chunks.exclude(pk__in=keep_ids).delete()
