<script lang="ts">
  import { onMount } from 'svelte';

  // The theme is applied before the first paint by the script in app.html; this button only switches it.
  let dark = $state(false);
  const apply = () => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; };

  onMount(() => {
    dark = document.documentElement.dataset.theme === 'dark';
    const system = matchMedia('(prefers-color-scheme: dark)');
    const follow = (event: MediaQueryListEvent) => {
      if (localStorage.getItem('theme')) return;
      dark = event.matches;
      apply();
    };
    system.addEventListener('change', follow);
    return () => system.removeEventListener('change', follow);
  });

  function toggle() {
    dark = !dark;
    try { localStorage.setItem('theme', dark ? 'dark' : 'light'); } catch { /* private mode: not remembered */ }
    apply();
  }
</script>

<button class="theme-toggle" onclick={toggle} aria-pressed={dark} aria-label="Dark mode" title={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
  {#if dark}
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
  {:else}
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
  {/if}
</button>
