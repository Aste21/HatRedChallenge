<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import ChatWidget from '#lib/chat/ChatWidget.svelte';
  import ThemeToggle from '#lib/ThemeToggle.svelte';
  import { chat } from '#lib/chat/session.svelte.ts';
  import { createLedger, provideLedger } from '#lib/ledger.ts';
  import { PRODUCT_NAME } from '#lib/brand.ts';
  import type { LayoutProps } from './$types';

  let { data, children }: LayoutProps = $props();
  // The account only changes through a full sign-out and sign-in, so the ledger is built once.
  // svelte-ignore state_referenced_locally
  provideLedger(createLedger(data.statement));
  // svelte-ignore state_referenced_locally
  onMount(() => chat.restore(data.account.id));

  const links = [
    { path: '/overview', label: 'Overview' },
    { path: '/proposals', label: 'Proposals' },
    { path: '/news', label: 'Business news' },
    { path: '/assistant', label: 'Chat' }
  ] as const;
</script>

<a class="skip" href="#workspace">Skip to content</a>
<header class="navigation">
  <div class="container nav-content">
    <a class="brand" href="/" aria-label="{PRODUCT_NAME} home">{PRODUCT_NAME}</a>
    <nav aria-label="Main navigation">
      {#each links as link}
        <a href={link.path} aria-current={page.url.pathname === link.path ? 'page' : undefined}>{link.label}</a>
      {/each}
    </nav>
    <div class="nav-tools">
      <ThemeToggle />
      <span class="account">{data.account.businessName}</span>
      <!-- A plain form: logging out reloads the page, so no data of this account stays in memory. -->
      <form method="POST" action="/logout"><button class="textbtn">Log out</button></form>
    </div>
  </div>
</header>
<main class="container" id="workspace">{@render children()}</main>
{#if !page.url.pathname.startsWith('/assistant')}<ChatWidget />{/if}
