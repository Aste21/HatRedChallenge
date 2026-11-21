<script lang="ts">
  import { onMount } from 'svelte';
  import ChatThread from '#lib/chat/ChatThread.svelte';
  import ConversationList from '#lib/chat/ConversationList.svelte';
  import { chat } from '#lib/chat/session.svelte.ts';
  import { PRODUCT_NAME } from '#lib/brand.ts';

  const suggestions = [
    { title: 'Why did cash fall', detail: 'in the summer of 2025?' },
    { title: 'Which bills are due', detail: 'at the start of next month?' },
    { title: 'How much cash', detail: 'could I safely set aside?' },
    { title: 'Explain the payment', detail: 'to Zurich every month' }
  ];
  let thread = $state<ChatThread>();

  onMount(() => { chat.refreshHistory(); });

  function newChat() {
    chat.newChat();
    thread?.focus();
  }
</script>

<div class="chat-layout">
  <aside class="panel chat-history" aria-label="Conversation history">
    <div class="chat-history-head">
      <h2>Conversations</h2>
      <button class="new-chat" onclick={newChat} disabled={!chat.messages.length && !chat.failure && !chat.conversationId}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>New chat
      </button>
    </div>
    <ConversationList onpick={() => thread?.focus()} />
  </aside>

  <section class="panel chat-app" aria-label="Chat with {PRODUCT_NAME}">
    <div class="chat-bar">
      <h1 class="chat-title">{chat.title || PRODUCT_NAME}</h1>
    </div>
    <ChatThread bind:this={thread} {suggestions} />
  </section>
</div>
