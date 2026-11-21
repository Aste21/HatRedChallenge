<script lang="ts">
  import { tick } from 'svelte';
  import Markdown from '#lib/Markdown.svelte';
  import CustomChart from '#lib/charts/CustomChart.svelte';
  import { customCharts } from '#lib/custom-charts.svelte.ts';
  import type { ChartSpec } from '#lib/charts/custom.ts';
  import { chat } from './session.svelte.ts';
  import { PRODUCT_NAME } from '#lib/brand.ts';

  type Suggestion = { title: string; detail: string };
  let {
    suggestions,
    compact = false,
    welcome = 'How can I help you today?',
    hint = 'Ask about your cashflow, upcoming bills or proposals. I explain — you decide.'
  }: { suggestions: Suggestion[]; compact?: boolean; welcome?: string; hint?: string } = $props();

  let copied = $state<number | null>(null);
  let scroller = $state<HTMLDivElement>();
  let field = $state<HTMLTextAreaElement>();

  $effect(() => {
    void chat.messages.length; void chat.pending; void chat.failure;
    tick().then(() => scroller?.scrollTo({ top: scroller.scrollHeight, behavior: 'smooth' }));
  });

  $effect(() => {
    void chat.draft;
    if (!field) return;
    field.style.height = 'auto';
    field.style.height = `${field.scrollHeight}px`;
  });

  export function focus() {
    field?.focus();
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      chat.send(chat.draft);
    }
  }

  let announcement = $state('');
  function addToOverview(spec: ChartSpec) {
    if (customCharts.add(spec)) announcement = `"${spec.title}" was added to Your charts on the overview.`;
  }

  async function copy(content: string, id: number) {
    await navigator.clipboard.writeText(content);
    copied = id;
    setTimeout(() => { if (copied === id) copied = null; }, 1500);
  }
</script>

<p class="sr-only" role="status">{announcement}</p>
<div class="chat-scroll" class:compact bind:this={scroller}>
  {#if chat.loading}
    <div class="chat-column chat-welcome" role="status"><p class="minor">Opening conversation…</p></div>
  {:else if !chat.messages.length}
    <div class="chat-column chat-welcome">
      <span class="avatar large" aria-hidden="true">€</span>
      <h2>{welcome}</h2>
      <p class="minor">{hint}</p>
      {#if chat.failure}<p class="chat-error" role="alert">{chat.failure}</p>{/if}
      <div class="chat-suggestions">
        {#each suggestions as suggestion (suggestion.title)}
          <button onclick={() => chat.send(`${suggestion.title} ${suggestion.detail}`)}>
            <strong>{suggestion.title}</strong><span>{suggestion.detail}</span>
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <div class="chat-column" aria-live="polite">
      {#each chat.messages as message (message.id)}
        {#if message.role === 'user'}
          <div class="message user"><p class="bubble"><span class="sr-only">You said: </span>{message.content}</p></div>
        {:else}
          <div class="message assistant">
            <span class="avatar" aria-hidden="true">€</span>
            <div class="assistant-body">
              <span class="sr-only">{PRODUCT_NAME}:</span>
              <Markdown source={message.content} />
              {#if message.chart}
                {#if compact}
                  <!-- The small assistant window has no room for an interactive chart. -->
                  <a class="chat-chart-link" href="/assistant">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>
                    <span><b>{message.chart.title}</b><small>Chart available in the Chat section — open it to see and save the chart</small></span>
                  </a>
                {:else}
                  {@const saved = customCharts.find(message.chart)}
                  <div class="chat-chart">
                    <CustomChart spec={message.chart} heading="h3" />
                    <div class="chat-chart-actions">
                      {#if saved}
                        <span class="chat-chart-saved">
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 5 5 9-10" /></svg>On your overview
                        </span>
                        <a href="/overview#your-charts">View on overview</a>
                      {:else}
                        <button class="add-chart" onclick={() => addToOverview(message.chart!)} disabled={customCharts.full}>
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>Add to overview
                        </button>
                        {#if customCharts.full}<span class="minor">Your overview is full. Delete a chart there first.</span>{/if}
                      {/if}
                    </div>
                  </div>
                {/if}
              {/if}
              <div class="message-actions">
                <button onclick={() => copy(message.content, message.id)} aria-label="Copy answer">
                  {#if copied === message.id}
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 5 5 9-10" /></svg>Copied
                  {:else}
                    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></svg>Copy
                  {/if}
                </button>
              </div>
            </div>
          </div>
        {/if}
      {/each}
      {#if chat.pending}
        <div class="message assistant" role="status">
          <span class="avatar" aria-hidden="true">€</span>
          <div class="typing"><span></span><span></span><span></span><span class="sr-only">{PRODUCT_NAME} is thinking…</span></div>
        </div>
      {/if}
      {#if chat.failure}
        <div class="chat-error" role="alert">
          <p>{chat.failure}</p>
          {#if chat.canRetry}<button onclick={() => chat.retry()}>Try again</button>{/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<div class="chat-column composer-area">
  <form class="composer" onsubmit={(event) => { event.preventDefault(); chat.send(chat.draft); }}>
    <label for={compact ? 'widget-question' : 'question'} class="sr-only">Your question</label>
    <textarea id={compact ? 'widget-question' : 'question'} rows="1" maxlength="2000"
      placeholder={compact ? 'Ask about this page…' : 'Ask about your cashflow…'}
      bind:this={field} bind:value={chat.draft} onkeydown={onKeydown}></textarea>
    {#if chat.pending}
      <button type="button" class="send" onclick={() => chat.stop()} aria-label="Stop answering">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="1.5" class="filled" /></svg>
      </button>
    {:else}
      <button class="send" disabled={!chat.draft.trim() || chat.loading} aria-label="Send question">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6" /></svg>
      </button>
    {/if}
  </form>
  <p class="chat-disclaimer">{PRODUCT_NAME} can make mistakes. Nothing is ever paid or moved without your approval.</p>
</div>
