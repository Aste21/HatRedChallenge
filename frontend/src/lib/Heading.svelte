<script lang="ts">
  let { title, period }: { title: string; period?: string } = $props();
</script>

<header class="page-heading">
  <h1>{title}</h1>
  {#if period}<p class="minor">{period}</p>{/if}
</header>
