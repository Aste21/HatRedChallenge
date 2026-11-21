<script lang="ts">
  import { onMount } from 'svelte';
  import { onNavigate } from '$app/navigation';
  import { page } from '$app/state';
  import ChatWidget from '#lib/chat/ChatWidget.svelte';
  import { chat } from '#lib/chat/session.svelte.ts';
  import './ledger.css';
  import type { LayoutProps } from './$types';

  let { children }: LayoutProps = $props();
  onMount(() => chat.restore());

  // Crossfade between pages where the browser supports View Transitions; the CSS turns it off for reduced motion.
  onNavigate((navigation) => {
    if (!document.startViewTransition || navigation.from?.url.pathname === navigation.to?.url.pathname) return;
    return new Promise((resolve) => {
      document.startViewTransition(async () => {
        resolve();
        await navigation.complete;
      });
    });
  });
  const links = [
    { path: '/', label: 'Overview' },
    { path: '/proposals', label: 'Proposals' },
    { path: '/news', label: 'Business news' },
    { path: '/assistant', label: 'Chat' }
  ] as const;
</script>

<a class="skip" href="#workspace">Skip to content</a>
<header class="navigation">
  <div class="container nav-content">
    <nav aria-label="Main navigation">
      {#each links as link}
        <a href={link.path} aria-current={page.url.pathname === link.path ? 'page' : undefined}>{link.label}</a>
      {/each}
    </nav>
    <span class="account">Pizzeria Amalfi</span>
  </div>
</header>
<main class="container" id="workspace">{@render children()}</main>
{#if !page.url.pathname.startsWith('/assistant')}<ChatWidget />{/if}
