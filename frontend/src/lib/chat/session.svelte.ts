import { collectPageContext } from './page-context.ts';

export type ChatMessage = { id: number; role: 'user' | 'assistant'; content: string };
export type ConversationSummary = { id: string; title: string; created_at: string; updated_at: string };
type StoredConversation = ConversationSummary & { messages: { role: 'user' | 'assistant'; content: string }[] };

const activeConversationKey = 'amalfi.chat.active';

async function errorMessage(response: Response, fallback: string): Promise<string> {
  const payload = await response.json().catch(() => ({}));
  return typeof payload.message === 'string' ? payload.message : fallback;
}

function rememberActive(id: string | null) {
  try {
    if (id) sessionStorage.setItem(activeConversationKey, id);
    else sessionStorage.removeItem(activeConversationKey);
  } catch { /* storage unavailable: the conversation just won't survive a reload */ }
}

/**
 * One chat session shared by the full chat page and the floating assistant, so a conversation
 * started on one page continues everywhere. Only mutated in the browser.
 */
class ChatSession {
  conversationId = $state<string | null>(null);
  title = $state('');
  messages = $state<ChatMessage[]>([]);
  draft = $state('');
  pending = $state(false);
  loading = $state(false);
  failure = $state('');
  conversations = $state<ConversationSummary[]>([]);
  historyStatus = $state<'idle' | 'loading' | 'ready' | 'failed'>('idle');

  canRetry = $derived(!this.pending && !!this.failure && this.messages.at(-1)?.role === 'user');

  #nextId = 0;
  #controller: AbortController | null = null;
  #loadToken = 0;
  #restored = false;

  /** Reopens the conversation that was active before a page reload. */
  restore() {
    if (this.#restored) return;
    this.#restored = true;
    let id: string | null = null;
    try { id = sessionStorage.getItem(activeConversationKey); } catch { /* ignore */ }
    if (id) this.open(id);
  }

  async refreshHistory() {
    if (!this.conversations.length) this.historyStatus = 'loading';
    try {
      const response = await fetch('/api/conversations');
      if (!response.ok) throw new Error();
      this.conversations = (await response.json()).conversations ?? [];
      this.historyStatus = 'ready';
    } catch {
      this.historyStatus = 'failed';
    }
  }

  async open(id: string) {
    if (id === this.conversationId && !this.failure) return;
    this.#cancelReply();
    const token = ++this.#loadToken;
    this.loading = true;
    this.failure = '';
    try {
      const response = await fetch(`/api/conversations/${id}`);
      if (token !== this.#loadToken) return;
      if (response.status === 404) {
        this.conversations = this.conversations.filter((conversation) => conversation.id !== id);
        this.newChat();
        return;
      }
      if (!response.ok) throw new Error(await errorMessage(response, 'This conversation could not be loaded.'));
      const conversation: StoredConversation = await response.json();
      if (token !== this.#loadToken) return;
      this.conversationId = conversation.id;
      this.title = conversation.title;
      this.messages = conversation.messages.map(({ role, content }) => ({ id: this.#nextId++, role, content }));
      this.draft = '';
      rememberActive(conversation.id);
    } catch (reason) {
      if (token === this.#loadToken) this.failure = reason instanceof Error ? reason.message : 'Something went wrong.';
    } finally {
      if (token === this.#loadToken) this.loading = false;
    }
  }

  newChat() {
    this.#cancelReply();
    this.#loadToken++;
    this.loading = false;
    this.conversationId = null;
    this.title = '';
    this.messages = [];
    this.failure = '';
    this.draft = '';
    rememberActive(null);
  }

  async send(text: string) {
    const question = text.trim();
    if (!question || this.pending || this.loading) return;
    this.messages.push({ id: this.#nextId++, role: 'user', content: question });
    this.draft = '';
    await this.#requestReply();
  }

  retry() {
    if (this.canRetry) this.#requestReply();
  }

  /** Stops waiting for the answer and puts the question back into the input field. */
  stop() {
    this.#controller?.abort();
  }

  async remove(id: string) {
    const response = await fetch(`/api/conversations/${id}`, { method: 'DELETE' }).catch(() => null);
    if (!response || (!response.ok && response.status !== 404)) return false;
    this.conversations = this.conversations.filter((conversation) => conversation.id !== id);
    if (id === this.conversationId) this.newChat();
    return true;
  }

  #cancelReply() {
    this.#controller?.abort();
    this.#controller = null;
    this.pending = false;
  }

  async #requestReply() {
    const question = this.messages.at(-1);
    if (question?.role !== 'user') return;
    const controller = new AbortController();
    this.#controller = controller;
    this.pending = true;
    this.failure = '';
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          conversation_id: this.conversationId,
          message: question.content,
          page_context: collectPageContext()
        }),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(await errorMessage(response, 'The assistant could not answer right now.'));
      const payload = await response.json();
      if (this.#controller !== controller) return;
      this.conversationId = payload.conversation_id;
      this.title = payload.title;
      this.messages.push({ id: this.#nextId++, role: 'assistant', content: payload.reply || 'I have no answer to that yet.' });
      rememberActive(payload.conversation_id);
      this.refreshHistory();
    } catch (reason) {
      if (controller.signal.aborted) {
        // Only the stop button leaves the question as the last message; New chat / Open replace the list.
        if (this.messages.at(-1)?.id === question.id) {
          this.messages.pop();
          this.draft = question.content;
        }
      } else {
        this.failure = reason instanceof Error ? reason.message : 'Something went wrong.';
      }
    } finally {
      if (this.#controller === controller) {
        this.#controller = null;
        this.pending = false;
      }
    }
  }
}

export const chat = new ChatSession();
