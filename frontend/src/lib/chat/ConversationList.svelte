<script lang="ts">
  import { chat } from './session.svelte.ts';

  let { compact = false, limit, onpick }: { compact?: boolean; limit?: number; onpick?: () => void } = $props();

  const visible = $derived(limit ? chat.conversations.slice(0, limit) : chat.conversations);
  const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [['minute', 60], ['hour', 24], ['day', 7], ['week', 4.35], ['month', 12]];

  function when(iso: string) {
    let value = (Date.parse(iso) - Date.now()) / 60_000;
    if (Math.abs(value) < 1) return 'just now';
    for (const [unit, size] of steps) {
      if (Math.abs(value) < size) return relative.format(Math.round(value), unit);
      value /= size;
    }
    return relative.format(Math.round(value), 'year');
  }

  let confirming = $state('');
  let notice = $state('');

  async function remove(id: string) {
    confirming = '';
    notice = (await chat.remove(id)) ? 'Conversation deleted.' : 'The conversation could not be deleted.';
  }

  async function pick(id: string) {
    onpick?.();
    await chat.open(id);
  }
</script>

{#if chat.historyStatus === 'loading'}
  <p class="minor history-note" role="status">Loading conversations…</p>
{:else if chat.historyStatus === 'failed' && !chat.conversations.length}
  <p class="minor history-note" role="alert">The chat history could not be loaded.
    <button class="textbtn" onclick={() => chat.refreshHistory()}>Try again</button></p>
{:else if !chat.conversations.length}
  <p class="minor history-note">No saved conversations yet. Your questions will appear here.</p>
{:else}
  <ul class="history" class:compact>
    {#each visible as conversation (conversation.id)}
      <li class:active={conversation.id === chat.conversationId}>
        <button class="history-open" onclick={() => pick(conversation.id)}
          aria-current={conversation.id === chat.conversationId ? 'true' : undefined}>
          <span class="history-title">{conversation.title}</span>
          <time class="history-time" datetime={conversation.updated_at}>{when(conversation.updated_at)}</time>
        </button>
        {#if compact}
          <!-- The compact list is for switching only; deleting happens on the Chat page. -->
        {:else if confirming === conversation.id}
          <span class="history-confirm">
            <button class="textbtn" onclick={() => remove(conversation.id)}>Delete</button>
            <button class="textbtn" onclick={() => confirming = ''}>Keep</button>
          </span>
        {:else}
          <button class="history-delete" onclick={() => confirming = conversation.id}
            aria-label={`Delete conversation “${conversation.title}”`} title="Delete conversation">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" /></svg>
          </button>
        {/if}
      </li>
    {/each}
  </ul>
{/if}
{#if !compact}<p class="sr-only" role="status">{notice}</p>{/if}
