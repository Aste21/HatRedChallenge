<script lang="ts">
  import Heading from '#lib/Heading.svelte';
  import type { PageProps } from './$types';
  let { data }: PageProps = $props();
</script>

<svelte:head><title>Business news</title></svelte:head>
<Heading title="Business news" />
<section class="panel">
  <div class="panel-head"><h2>Relevant articles</h2><a href="/news" data-sveltekit-reload>Refresh</a></div>
  {#each data.articles as article}
    <article class="news-item">
      <p class="minor">{article.source}{#if article.published} · {article.published}{/if}</p>
      <h3><a href={article.url} target="_blank" rel="noreferrer">{article.title}</a></h3>
      {#if article.summary}<p>{article.summary}</p>{/if}
      {#if article.reason}<p><b>Business impact</b> · {article.reason}</p>{/if}
    </article>
  {:else}
    <p class="note" role="status">
      {#if data.feed === 'unconfigured'}The news service has not been connected.
      {:else if data.feed === 'unavailable'}The news service is unavailable. Try refreshing.
      {:else}There are no relevant articles yet.{/if}
    </p>
  {/each}
</section>
