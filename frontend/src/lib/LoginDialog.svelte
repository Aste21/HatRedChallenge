<script lang="ts">
  import { enhance } from '$app/forms';
  import { PRODUCT_NAME } from '#lib/brand.ts';

  let { open = $bindable(false) }: { open?: boolean } = $props();

  let dialog = $state<HTMLDialogElement>();
  let username = $state<HTMLInputElement>();
  let error = $state('');
  let pending = $state(false);

  // showModal() gives focus trapping, Escape to close and an inert page behind the dialog for free.
  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) {
      error = '';
      dialog.showModal();
      username?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  });

  function closeOnBackdrop(event: MouseEvent) {
    if (event.target === dialog) open = false;
  }
</script>

<dialog class="login-dialog" bind:this={dialog} onclose={() => (open = false)} onclick={closeOnBackdrop} aria-labelledby="login-title">
  <div class="login-dialog-body">
    <div class="panel-head">
      <h2 id="login-title">Log in to {PRODUCT_NAME}</h2>
      <button class="dialog-close" onclick={() => (open = false)} aria-label="Close">×</button>
    </div>
    <p class="note">See your cash flow, the forecast and the proposals waiting for you.</p>
    <!-- Without JavaScript this is a normal form post to /login; with it, errors stay in the dialog and a
         successful login reloads the app, so it starts clean for this account. -->
    <form method="POST" action="/login" class="auth-form" use:enhance={() => {
      pending = true;
      error = '';
      return async ({ result }) => {
        pending = false;
        if (result.type === 'redirect') location.assign(result.location);
        else if (result.type === 'failure') error = result.data?.missing ? 'Please enter your username and password.' : 'The username or password is not right. Please try again.';
        else error = 'Logging in did not work right now. Please try again in a moment.';
      };
    }}>
      <label>Username
        <input bind:this={username} name="username" autocomplete="username" required aria-invalid={error ? 'true' : undefined} aria-describedby={error ? 'dialog-login-error' : undefined} />
      </label>
      <label>Password
        <input name="password" type="password" autocomplete="current-password" required aria-invalid={error ? 'true' : undefined} aria-describedby={error ? 'dialog-login-error' : undefined} />
      </label>
      {#if error}<p class="form-error" id="dialog-login-error" role="alert">{error}</p>{/if}
      <button class="action" disabled={pending}>{pending ? 'Logging in…' : 'Log in'}</button>
    </form>
    <p class="demo-hint"><b>Try the demo</b> · username <code>amalfi</code>, password <code>amalfi</code> (Pizzeria Amalfi, Frankfurt)</p>
  </div>
</dialog>
