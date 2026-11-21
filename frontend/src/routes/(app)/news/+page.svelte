<script lang="ts">
  import { invalidateAll } from '$app/navigation';
  import Heading from '#lib/Heading.svelte';
  import { describeEvent, type Article, type NewsImpact } from '#lib/forecast.ts';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
  let working = $state('');
  let notice = $state('');
  let impacts = $derived(new Map<string, NewsImpact>(data.impacts.map((impact) => [impact.article_id, impact])));

  async function checkImpact(article: Article) {
    working = article.id;
    notice = '';
    try {
      const response = await fetch('/api/news/impacts', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ article_id: article.id, title: article.title, summary: article.summary ?? '' })
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        notice = body?.message ?? 'The forecast could not check this article. Please try again.';
        return;
      }
      notice = body?.events?.length
        ? 'Done. Your forecast and proposals now take this article into account.'
        : 'Checked. This article does not change your expected cash flow.';
      await invalidateAll();
    } catch {
      notice = 'The forecast could not check this article. Please check your connection and try again.';
    } finally {
      working = '';
    }
  }

  async function removeImpact(article: Article) {
    working = article.id;
    notice = '';
    try {
      const response = await fetch(`/api/news/impacts/${article.id}`, { method: 'DELETE' });
      notice = response.ok ? 'Removed. Your forecast no longer uses this article.' : 'The article could not be removed. Please try again.';
      await invalidateAll();
    } catch {
      notice = 'The article could not be removed. Please check your connection and try again.';
    } finally {
      working = '';
    }
  }
</script>

<svelte:head><title>Business news</title></svelte:head>
<Heading title="Business news" />
<section class="panel">
  <div class="panel-head"><h2>Relevant articles</h2><a href="/news" data-sveltekit-reload>Refresh</a></div>
  {#each data.articles as article (article.id ?? article.url)}
    {@const impact = impacts.get(article.id)}
    <article class="news-item">
      <p class="minor">{article.source}{#if article.published} · {article.published}{/if}</p>
      <h3><a href={article.url} target="_blank" rel="noreferrer">{article.title}</a></h3>
      {#if article.summary}<p>{article.summary}</p>{/if}
      {#if article.reason}<p><b>Business impact</b> · {article.reason}</p>{/if}
      {#if article.id}
        <div class="impact">
          {#if working === article.id}
            <p class="minor" role="status">Your assistant is checking how this affects your cash flow. This can take a few seconds…</p>
          {:else if impact}
            {#if impact.events.length}
              <p><b>In your forecast</b></p>
              <ul>
                {#each impact.events as event, position (position)}
                  <li>
                    <span class="tag" class:estimate={event.certainty !== 'official'}>{event.certainty === 'official' ? 'Confirmed' : 'Estimate'}</span>
                    <span>{describeEvent(event)}{#if event.why}<span class="minor"> · {event.why}</span>{/if}</span>
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="minor">Checked: no change to your expected cash flow.</p>
            {/if}
            <div class="actions">
              <a href="/">See the forecast</a>
              <button disabled={working !== ''} onclick={() => removeImpact(article)}>Remove from forecast</button>
            </div>
          {:else}
            <button disabled={working !== ''} onclick={() => checkImpact(article)}>Check impact on my forecast</button>
          {/if}
        </div>
      {/if}
    </article>
  {:else}
    <p class="note" role="status">
      {#if data.feed === 'unconfigured'}The news service has not been connected.
      {:else if data.feed === 'unavailable'}The news service is unavailable. Try refreshing.
      {:else}There are no relevant articles yet.{/if}
    </p>
  {/each}
</section>
<p class="minor" role="status">{notice}</p>
