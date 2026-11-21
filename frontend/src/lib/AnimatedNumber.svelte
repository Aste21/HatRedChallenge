<script lang="ts">
  import { Tween, prefersReducedMotion } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';

  let { value, format }: { value: number; format: (value: number) => string } = $props();

  // Counts up from zero on first show and glides to new values (e.g. a scenario switch); instant under reduced motion.
  const shown = new Tween(0, { duration: 480, easing: cubicOut });
  $effect(() => { shown.set(value, { duration: prefersReducedMotion.current ? 0 : 480 }); });
</script>

<span aria-hidden="true">{format(shown.current)}</span><span class="sr-only">{format(value)}</span>
