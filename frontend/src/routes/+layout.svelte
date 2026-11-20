<script lang="ts">
  import { page } from '$app/state';
  import './ledger.css';
  import type { LayoutProps } from './$types';

  let { children }: LayoutProps = $props();
  const links = [
    { path: '/', label: 'Cashflow' },
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
