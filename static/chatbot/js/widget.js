document.addEventListener('DOMContentLoaded', () => {
    const widget = document.querySelector('.them-ai');
    if (!widget) return;

    const launcher = widget.querySelector('.them-ai-launcher');
    const panel = widget.querySelector('.them-ai-panel');
    const closeButton = widget.querySelector('.them-ai-close');
    const resetButton = widget.querySelector('.them-ai-reset');
    const form = widget.querySelector('.them-ai-form');
    const input = widget.querySelector('#them-ai-input');
    const sendButton = widget.querySelector('.them-ai-send');
    const messages = widget.querySelector('.them-ai-messages');
    const status = widget.querySelector('.them-ai-status');
    const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;
    const chatUrl = widget.dataset.chatUrl;
    let conversationId = null;
    let pending = false;

    const setOpen = (open) => {
        panel.hidden = !open;
        launcher.setAttribute('aria-expanded', String(open));
        launcher.setAttribute('aria-label', open ? 'Close TheMenu AI chat' : 'Open TheMenu AI chat');
        if (open) input.focus();
        else launcher.focus();
    };

    const addMessage = (text, role, sources = []) => {
        const message = document.createElement('p');
        message.className = `them-ai-message ${role === 'user' ? 'them-ai-user' : 'them-ai-assistant'}`;
        message.textContent = text;
        messages.append(message);
        if (sources.length) {
            const sourceList = document.createElement('p');
            sourceList.className = 'them-ai-sources';
            sourceList.textContent = `Sources: ${sources.map((source) => source.title).join(', ')}`;
            messages.append(sourceList);
        }
        messages.scrollTop = messages.scrollHeight;
        return message;
    };

    const submitMessage = async (text, requestId = crypto.randomUUID()) => {
        if (pending || !text.trim()) return;
        pending = true;
        sendButton.disabled = true;
        status.textContent = 'TheMenu AI is preparing a response…';
        const loading = addMessage('Thinking…', 'assistant');
        try {
            const response = await fetch(chatUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                    request_id: requestId,
                }),
            });
            const data = await response.json();
            loading.remove();
            if (!response.ok) throw new Error(data.error || 'Unable to send your message.');
            conversationId = data.conversation_id;
            addMessage(data.answer, 'assistant', data.sources || []);
            status.textContent = '';
        } catch (error) {
            loading.remove();
            status.textContent = error.message || 'A network error occurred. Please retry.';
            const retry = document.createElement('button');
            retry.type = 'button';
            retry.className = 'them-ai-retry';
            retry.textContent = 'Retry';
            retry.addEventListener('click', () => {
                retry.remove();
                submitMessage(text, requestId);
            }, { once: true });
            messages.append(retry);
            messages.scrollTop = messages.scrollHeight;
        } finally {
            pending = false;
            sendButton.disabled = false;
        }
    };

    launcher.addEventListener('click', () => setOpen(panel.hidden));
    closeButton.addEventListener('click', () => setOpen(false));
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text || pending) return;
        input.value = '';
        addMessage(text, 'user');
        submitMessage(text);
    });
    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });
    widget.querySelectorAll('.them-ai-suggestions button').forEach((button) => {
        button.addEventListener('click', () => {
            input.value = button.textContent;
            form.requestSubmit();
        });
    });
    resetButton.addEventListener('click', async () => {
        if (pending) return;
        const oldConversationId = conversationId;
        conversationId = null;
        messages.replaceChildren();
        addMessage('Conversation cleared. What would you like to know?', 'assistant');
        status.textContent = '';
        if (oldConversationId) {
            try {
                const response = await fetch(`/api/chatbot/conversations/${oldConversationId}/`, {
                    method: 'DELETE',
                    credentials: 'same-origin',
                    headers: {'X-CSRFToken': csrfToken},
                });
                if (!response.ok && response.status !== 404) {
                    throw new Error(`Conversation deletion failed (${response.status}).`);
                }
            } catch (error) {
                status.textContent = 'The conversation was cleared here but could not be removed from the server.';
            }
        }
    });
});
