<script lang="ts">
  import { page } from '$app/state';
  import ThemeToggle from '#lib/ThemeToggle.svelte';
  import { PRODUCT_NAME } from '#lib/brand.ts';
  import type { PageProps } from './$types';

  let { form }: PageProps = $props();
  let next = $derived(page.url.searchParams.get('next'));
</script>

<svelte:head><title>Log in · {PRODUCT_NAME}</title><meta name="robots" content="noindex" /></svelte:head>
<div class="auth-page">
  <header class="auth-head container">
    <a class="brand" href="/">{PRODUCT_NAME}</a>
    <ThemeToggle />
  </header>
  <main class="auth-card panel enter" id="workspace">
    <h1>Log in</h1>
    <p class="note">Welcome back. Log in to see your business's cash flow.</p>
    {#if next}<p class="minor" role="status">Please log in to continue.</p>{/if}
    <!-- A plain form on purpose: logging in reloads the app, so it starts clean for this account. -->
    <form method="POST" action={next ? `?next=${encodeURIComponent(next)}` : undefined} class="auth-form">
      <label>Username
        <input name="username" autocomplete="username" required value={form?.username ?? ''}
          aria-invalid={form?.incorrect || form?.missing ? 'true' : undefined} aria-describedby={form ? 'login-error' : undefined} />
      </label>
      <label>Password
        <input name="password" type="password" autocomplete="current-password" required
          aria-invalid={form?.incorrect ? 'true' : undefined} aria-describedby={form ? 'login-error' : undefined} />
      </label>
      {#if form?.incorrect}<p class="form-error" id="login-error" role="alert">The username or password is not right. Please try again.</p>
      {:else if form?.missing}<p class="form-error" id="login-error" role="alert">Please enter your username and password.</p>{/if}
      <button class="action">Log in</button>
    </form>
    <p class="demo-hint"><b>Demo account</b> · username <code>amalfi</code>, password <code>amalfi</code> (Pizzeria Amalfi, Frankfurt)</p>
  </main>
</div>
