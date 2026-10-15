import math
import json

from django.conf import settings
from django.db import connection

from chatbot.models import DocumentChunk
from chatbot.services.providers import embed_text


def _cosine_distance(left, right):
    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 1.0
    return 1.0 - (dot_product / (left_norm * right_norm))


def retrieve_chunks(question):
    active_chunks = DocumentChunk.objects.filter(
        document__active=True, embedding__isnull=False
    ).select_related('document')
    if not active_chunks.exists():
        return []
    query_vector = embed_text(question)

    if connection.vendor == 'postgresql':
        vector_literal = json.dumps(query_vector, separators=(',', ':'))
        return list(
            active_chunks.extra(
                select={'distance': 'embedding <=> %s::vector'},
                select_params=(vector_literal,),
                where=['embedding <=> %s::vector <= %s'],
                params=(vector_literal, settings.CHATBOT_MAX_COSINE_DISTANCE),
            )
            .order_by('distance')[:settings.CHATBOT_TOP_K]
        )

    ranked = []
    for chunk in active_chunks:
        distance = _cosine_distance(chunk.embedding, query_vector)
        if distance <= settings.CHATBOT_MAX_COSINE_DISTANCE:
            chunk.distance = distance
            ranked.append(chunk)
    ranked.sort(key=lambda chunk: chunk.distance)
    return ranked[:settings.CHATBOT_TOP_K]


def source_metadata(chunks):
    seen = set()
    sources = []
    for chunk in chunks:
        document = chunk.document
        key = (document.source_type, document.source_identifier)
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            'title': document.title,
            'source_type': document.source_type,
        })
    return sources
