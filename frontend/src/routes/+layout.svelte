<script lang="ts">
  import { onNavigate } from '$app/navigation';
  import './ledger.css';
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

{@render children()}
