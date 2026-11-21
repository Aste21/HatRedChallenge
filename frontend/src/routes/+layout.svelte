<script lang="ts">
  import { onNavigate } from '$app/navigation';
  import './ledger.css';
  import { PRODUCT_NAME } from '#lib/brand.ts';
  import type { LayoutProps } from './$types';

  let { children }: LayoutProps = $props();

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
</script>

<!-- One fixed browser-tab title on every page. -->
<svelte:head><title>{PRODUCT_NAME}</title></svelte:head>

{@render children()}
