<script lang="ts">
  import { tick } from 'svelte';
  import { page } from '$app/state';
  import ChatThread from './ChatThread.svelte';
  import ConversationList from './ConversationList.svelte';
  import { chat } from './session.svelte.ts';

  type Suggestion = { title: string; detail: string };
  const pages: Record<string, { name: string; suggestions: Suggestion[] }> = {
    '/overview': { name: 'Overview', suggestions: [
      { title: 'Explain this page', detail: 'in simple words' },
      { title: 'Which month was', detail: 'the weakest for my cash?' }
    ] },
    '/proposals': { name: 'Proposals', suggestions: [
      { title: 'Explain these proposals', detail: 'in simple words' },
      { title: 'What happens', detail: 'if I approve the deposit?' }
    ] },
    '/news': { name: 'Business news', suggestions: [
      { title: 'What do these articles', detail: 'mean for my pizzeria?' },
      { title: 'Is any of this news', detail: 'about taxes?' }
    ] }
  };
  const fallback = { name: 'current', suggestions: [{ title: 'Explain this page', detail: 'in simple words' }] };

  let open = $state(false);
  let view = $state<'chat' | 'history'>('chat');
  let thread = $state<ChatThread>();
  let launcher = $state<HTMLButtonElement>();
  const current = $derived(pages[page.url.pathname] ?? fallback);

  async function toggle() {
    open = !open;
    if (!open) return;
    view = 'chat';
    chat.refreshHistory();
    await tick();
    thread?.focus();
  }

  function close() {
    open = false;
    launcher?.focus();
  }

  async function showChat() {
    view = 'chat';
    await tick();
    thread?.focus();
  }

  function startNewChat() {
    chat.newChat();
    showChat();
  }

  function toggleHistory() {
    if (view === 'history') return showChat();
    view = 'history';
    chat.refreshHistory();
  }
</script>

<svelte:window onkeydown={(event) => { if (open && event.key === 'Escape') close(); }} />

{#if open}
  <section class="assistant-popover" id="assistant-popover" aria-label="CFO assistant">
    <header class="popover-head">
      <div class="popover-heading">
        <h2>{view === 'history' ? 'Your conversations' : chat.title || 'CFO assistant'}</h2>
        <p class="popover-sees">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></svg>
          Can see your {current.name} page
        </p>
      </div>
      <div class="popover-tools">
        <button onclick={toggleHistory} aria-pressed={view === 'history'} aria-label="Show conversation history" title="History">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></svg>
        </button>
        <button onclick={startNewChat} aria-label="Start a new chat" title="New chat">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        </button>
        <a href="/assistant" onclick={() => open = false} aria-label="Open the full chat page" title="Open full chat">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg>
        </a>
        <button onclick={close} aria-label="Close the assistant" title="Close">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
        </button>
      </div>
    </header>

    {#if view === 'history'}
      <div class="popover-history">
        <ConversationList compact limit={8} onpick={showChat} />
        <a class="popover-all" href="/assistant" onclick={() => open = false}>See all conversations</a>
      </div>
    {:else}
      <ChatThread bind:this={thread} compact suggestions={current.suggestions}
        welcome="Questions about this page?"
        hint={`I can read what is shown on your ${current.name} page and explain it. You decide what happens.`} />
    {/if}
  </section>
{/if}

<button class="assistant-launcher" bind:this={launcher} onclick={toggle}
  aria-expanded={open} aria-controls="assistant-popover">
  {#if open}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg><span>Close</span>
  {:else}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" /></svg><span>Ask the assistant</span>
  {/if}
</button>
