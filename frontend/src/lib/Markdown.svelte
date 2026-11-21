<script lang="ts">
  import { parseMarkdown, type Inline } from './markdown.ts';
  let { source }: { source: string } = $props();
  const blocks = $derived(parseMarkdown(source));
</script>

{#snippet text(parts: Inline)}{#each parts as part, index (index)}{#if part.strong}<strong>{part.text}</strong>{:else}{part.text}{/if}{/each}{/snippet}

{#each blocks as block, index (index)}
  {#if block.kind === 'heading'}<h3>{@render text(block.text)}</h3>
  {:else if block.kind === 'list' && block.ordered}<ol>{#each block.items as item, index (index)}<li>{@render text(item)}</li>{/each}</ol>
  {:else if block.kind === 'list'}<ul>{#each block.items as item, index (index)}<li>{@render text(item)}</li>{/each}</ul>
  {:else}<p>{#each block.lines as line, index (index)}{#if index}<br />{/if}{@render text(line)}{/each}</p>{/if}
{/each}
