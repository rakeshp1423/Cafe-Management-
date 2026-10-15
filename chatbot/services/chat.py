import re

from django.conf import settings
from core.models import MenuItem
from chatbot.models import ChatConversation, ChatMessage, ChatTurn
from chatbot.services.providers import generate_answer
from chatbot.services.retrieval import retrieve_chunks, source_metadata


UNKNOWN_ANSWER = (
    "I couldn't find that in the café's verified information. I can help with the "
    'menu or explain how to use the reservation form.'
)
MENU_TERMS = re.compile(
    r'\b(menu|dish|dishes|food|item|items|price|prices|cost|vegetarian|vegan|'
    r'ingredient|ingredients|allergen|allergens|under|below|less than|available)\b',
    re.IGNORECASE,
)
BUDGET_QUERY = re.compile(
    r'\b(under|below|less than|cheaper than|up to|within)\s*'
    r'(?:₹\s*|rs\.?\s*)?(\d+(?:\.\d{1,2})?)',
    re.IGNORECASE,
)
PRICE_QUERY = re.compile(r'\b(price|prices|cost|costs|how much)\b', re.IGNORECASE)


def _conversation_owner(request):
    if request.user.is_authenticated:
        return {'user': request.user, 'session_key': None}
    if not request.session.session_key:
        request.session.create()
        request.session.modified = True
    return {'user': None, 'session_key': request.session.session_key}


def _live_menu(question):
    if not MENU_TERMS.search(question):
        return [], ''

    items = list(MenuItem.objects.all().order_by('name')[:50])
    if not items:
        return [], ''

    live_text = '\n'.join(
        f'- {item.name}: {(item.description.strip() or "No description recorded.")[:400]}; '
        f'current price ₹{item.price}.'
        for item in items
    )
    if MenuItem.objects.count() > len(items):
        live_text += '\nOnly the first 50 menu items are included in this context.'
    return items, live_text


def _budget_answer(question):
    match = BUDGET_QUERY.search(question)
    if not match:
        return None

    operator, raw_limit = match.groups()
    query = MenuItem.objects.all()
    if operator.lower() in {'up to', 'within'}:
        query = query.filter(price__lte=raw_limit)
    else:
        query = query.filter(price__lt=raw_limit)

    total_matches = query.count()
    items = list(query.order_by('price', 'name')[:100])
    if not items:
        answer = f'No currently listed menu items are priced {operator} ₹{raw_limit}.'
    else:
        answer = 'Current menu items matching your price range:\n' + '\n'.join(
            f'- {item.name}: ₹{item.price}' for item in items
        )
        if total_matches > len(items):
            answer += f'\nShowing the first {len(items)} of {total_matches} matching items.'
    return answer, [{'title': 'Current Menu', 'source_type': 'menu'}]


def _price_answer(question):
    if not PRICE_QUERY.search(question):
        return None

    normalized_question = question.casefold()
    mentioned_items = [
        item for item in MenuItem.objects.all()
        if item.name.casefold() in normalized_question
    ]
    if mentioned_items:
        answer = 'Current listed prices:\n' + '\n'.join(
            f'- {item.name}: ₹{item.price}' for item in mentioned_items
        )
    else:
        answer = 'Which menu item would you like me to check the current listed price for?'
    return answer, [{'title': 'Current Menu', 'source_type': 'menu'}]


def _known_answer(question):
    if re.search(r'\b(vegetarian|vegan)\b', question, re.IGNORECASE):
        return (
            'The menu does not store verified vegetarian or vegan classifications, '
            'so I cannot reliably identify those dishes. Please check with the café '
            'before ordering.',
            [{'title': 'Current Menu', 'source_type': 'menu'}],
        )
    if re.search(r'\b(allergen|allergens|allergy|allergies)\b', question, re.IGNORECASE):
        return (
            'The menu does not contain verified allergen information. Please contact '
            'the café directly before ordering.',
            [{'title': 'Current Menu', 'source_type': 'menu'}],
        )
    if re.search(r'\b(opening hours|hours|open|close|location|address|phone|contact)\b',
                 question, re.IGNORECASE):
        return (
            "The café's verified opening hours and contact details are not recorded "
            'in the information available to me.',
            [],
        )
    if re.search(
        r'\b(reserv\w*|book a table|table booking)\b',
        question,
        re.IGNORECASE,
    ):
        return (
            'To request a table, sign in and open Book a Table (or visit /reserve/). '
            'Choose a date and time, enter 1-8 guests, and optionally add a special '
            'request before submitting. This submits a request; the site does not check '
            'availability or automatically confirm bookings. For parties larger '
            'than 8, contact the café directly.',
            [{'title': 'Reservation form', 'source_type': 'reservation'}],
        )
    if re.search(r'\b(available|availability)\b', question, re.IGNORECASE):
        return (
            'The menu does not track live item availability, so I cannot confirm what '
            'is available right now. Please check with the café.',
            [{'title': 'Current Menu', 'source_type': 'menu'}],
        )
    return None


def answer_question(request, question, conversation):
    known_answer = _known_answer(question)
    if known_answer:
        return {'answer': known_answer[0], 'sources': known_answer[1]}

    budget_answer = _budget_answer(question)
    if budget_answer:
        return {'answer': budget_answer[0], 'sources': budget_answer[1]}

    price_answer = _price_answer(question)
    if price_answer:
        return {'answer': price_answer[0], 'sources': price_answer[1]}

    if MENU_TERMS.search(question) and not MenuItem.objects.exists():
        return {
            'answer': 'There are currently no menu items recorded in the live menu.',
            'sources': [{'title': 'Current Menu', 'source_type': 'menu'}],
        }

    chunks = retrieve_chunks(question)
    _, live_menu = _live_menu(question)
    if not chunks and not live_menu:
        return {'answer': UNKNOWN_ANSWER, 'sources': []}

    context_parts = []
    selected_chunks = []
    used_chars = 0
    context_limit = max(1, settings.CHATBOT_MAX_CONTEXT_CHARS)
    for chunk in chunks:
        section = f'Source: {chunk.document.title}\n{chunk.text}'
        separator = '\n\n' if context_parts else ''
        available = context_limit - used_chars - len(separator)
        if available <= 0:
            break
        context_parts.append(section[:available])
        selected_chunks.append(chunk)
        used_chars += len(separator) + min(len(section), available)
        if len(section) > available:
            break

    live_menu_included = False
    if live_menu and used_chars < context_limit:
        section = f'Current menu data from the live database:\n{live_menu}'
        separator = '\n\n' if context_parts else ''
        available = context_limit - used_chars - len(separator)
        if available > 0:
            context_parts.append(section[:available])
            live_menu_included = True
    context = '\n\n'.join(context_parts)
    history = list(
        conversation.messages.order_by('-created_at', '-pk')[:settings.CHATBOT_HISTORY_MESSAGES]
    ) if conversation else []
    history.reverse()
    history = [{'role': message.role, 'content': message.content} for message in history]
    return {
        'answer': generate_answer(question, context, history),
        'sources': source_metadata(selected_chunks) + (
            [{'title': 'Current Menu', 'source_type': 'menu'}] if live_menu_included else []
        ),
    }


def get_owned_conversation(request, conversation_id):
    return ChatConversation.objects.filter(
        id=conversation_id, **_conversation_owner(request)
    ).first()


def get_existing_turn(request, request_id):
    owner = _conversation_owner(request)
    return ChatTurn.objects.select_related('conversation').filter(
        request_id=request_id,
        conversation__user=owner.get('user'),
        conversation__session_key=owner.get('session_key'),
    ).first()


def save_turn(request, question, answer, sources, conversation, request_id):
    if conversation is None:
        owner = _conversation_owner(request)
        conversation = ChatConversation.objects.create(**owner)
    ChatTurn.objects.create(
        request_id=request_id,
        conversation=conversation,
        question=question,
        answer=answer,
        sources=sources,
    )
    ChatMessage.objects.bulk_create([
        ChatMessage(conversation=conversation, role='user', content=question),
        ChatMessage(
            conversation=conversation,
            role='assistant',
            content=answer,
            sources=sources,
        ),
    ])
    conversation.save(update_fields=['updated_at'])
    old_messages = list(
        conversation.messages.order_by('-created_at', '-pk')[40:].values_list('pk', flat=True)
    )
    if old_messages:
        ChatMessage.objects.filter(pk__in=old_messages).delete()
    old_turns = list(
        conversation.turns.order_by('-created_at', '-pk')[20:].values_list('pk', flat=True)
    )
    if old_turns:
        ChatTurn.objects.filter(pk__in=old_turns).delete()
    return conversation
