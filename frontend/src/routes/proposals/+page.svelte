<script lang="ts">
  import { invalidateAll } from '$app/navigation';
  import Heading from '#lib/Heading.svelte';
  import { dateLabel } from '#lib/ledger.ts';
  import { euro, type Proposal, type ProposalStatus } from '#lib/forecast.ts';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
  let confirming = $state('');
  let saving = $state('');
  let notice = $state('');

  const statusLabels: Record<ProposalStatus, string> = {
    awaiting_approval: 'Awaiting approval',
    approved: 'Approved',
    declined: 'Declined',
    superseded: 'Another option chosen'
  };
  const categoryLabels: Record<Proposal['kind'], string> = {
    fixed_term_deposit: 'Fixed-term deposit',
    credit_line: 'Credit line'
  };

  async function decide(proposal: Proposal, decision: 'approved' | 'declined') {
    confirming = '';
    saving = proposal.id;
    notice = '';
    try {
      const response = await fetch(`/api/proposals/${encodeURIComponent(proposal.id)}/decision`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ decision })
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        notice = body?.message ?? 'The decision could not be saved. Please try again.';
        return;
      }
      notice = decision === 'declined'
        ? 'Declined. Nothing will happen.'
        : body?.notification_status === 'sent'
          ? 'Approved. The simulated transaction is recorded and a confirmation e-mail was sent.'
          : 'Approved. The simulated transaction is recorded and a confirmation was added to your notifications.';
      await invalidateAll();
    } catch {
      notice = 'The decision could not be saved. Please check your connection and try again.';
    } finally {
      saving = '';
    }
  }
</script>

<svelte:head><title>Proposals</title></svelte:head>
<Heading title="Proposals" period="Simulated decisions" />

{#await data.board}
  <p class="note" role="status">Your CFO assistant is checking the forecast and preparing proposals. This can take a few seconds…</p>
{:then loaded}
  {#if !loaded.ok}
    <p class="note" role="status">Proposals are not available right now: {loaded.message} Try refreshing in a moment.</p>
  {:else}
    {@const board = loaded.data}
    <p class="note">
      Based on your balance of {euro(board.start_balance)} on {dateLabel(board.as_of)}. Nothing happens until you approve,
      and every approval is simulated: no real money moves. Offers and rates are illustrative demo figures.
    </p>
    {#each board.warnings as warning (warning)}<p class="note" role="status">{warning}</p>{/each}
    <div class="proposal-grid">
      {#each board.proposals as proposal (proposal.id)}
        <article class="panel proposal">
          <div class="panel-head"><p class="eyebrow">{categoryLabels[proposal.kind]}</p><span class="status">{statusLabels[proposal.status]}</span></div>
          <h2>{proposal.title}</h2><strong class="amount">{euro(proposal.amount)}</strong>
          <dl>
            <dt>What we see</dt><dd>{proposal.analysis}</dd>
            <dt>What we suggest</dt><dd>{proposal.recommendation}</dd>
            <dt>Why this amount</dt><dd>{proposal.rationale}</dd>
            <dt>On approval</dt><dd>{proposal.on_approval}</dd>
          </dl>
          {#if proposal.status === 'awaiting_approval'}
            {#if saving === proposal.id}
              <p class="decision" role="status">Saving your decision…</p>
            {:else if confirming === proposal.id}
              <div class="confirm">
                <p>Approve this simulated {categoryLabels[proposal.kind].toLowerCase()} of {euro(proposal.amount)}?</p>
                <button class="action" onclick={() => decide(proposal, 'approved')}>Confirm approval</button>
                <button onclick={() => confirming = ''}>Cancel</button>
              </div>
            {:else}
              <div class="actions">
                <button class="action" disabled={saving !== ''} onclick={() => confirming = proposal.id}>Approve</button>
                <button disabled={saving !== ''} onclick={() => decide(proposal, 'declined')}>Decline</button>
              </div>
            {/if}
          {:else if proposal.status === 'superseded'}
            <p class="decision">You already chose another option that uses the same cash.</p>
          {:else}
            <p class="decision">{statusLabels[proposal.status]}{#if proposal.decided_at} on {dateLabel(proposal.decided_at)}{/if} · Simulation recorded</p>
          {/if}
        </article>
      {:else}
        <p class="note">No proposals right now: the forecast shows no spare cash to place and no cash gap to cover.</p>
      {/each}
    </div>
    {#if board.notification_draft}
      <details class="panel">
        <summary>Message drafted by your assistant</summary>
        <h3>{board.notification_draft.subject}</h3>
        <p class="draft">{board.notification_draft.body}</p>
      </details>
    {/if}
  {/if}
{/await}
<p class="minor" role="status">{notice}</p>
