<script lang="ts">
  import { invalidateAll } from '$app/navigation';
  import Heading from '#lib/Heading.svelte';
  import AnimatedNumber from '#lib/AnimatedNumber.svelte';
  import AmountWaterfall from '#lib/charts/AmountWaterfall.svelte';
  import DepositComparison from '#lib/charts/DepositComparison.svelte';
  import { dateLabel } from '#lib/ledger.ts';
  import { euro, type Proposal, type ProposalStatus, type StoredNotification } from '#lib/forecast.ts';
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
  const deliveryLabels: Record<StoredNotification['status'], string> = {
    queued: 'In your inbox',
    sent: 'E-mail sent',
    failed: 'E-mail failed, kept here'
  };
  const reference = (id: string) => 'SIM-' + id.slice(0, 8).toUpperCase();
  const dateTime = (iso: string) =>
    new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));

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
      const recorded = body?.transaction_id ? ` (reference ${reference(body.transaction_id)})` : '';
      notice = decision === 'declined'
        ? 'Declined. Nothing will happen.'
        : body?.notification_status === 'sent'
          ? `Approved. The simulated transaction is recorded${recorded} and a confirmation e-mail was sent.`
          : `Approved. The simulated transaction is recorded${recorded} and a confirmation was added to your notifications.`;
      await invalidateAll();
    } catch {
      notice = 'The decision could not be saved. Please check your connection and try again.';
    } finally {
      saving = '';
    }
  }
</script>

<Heading title="Proposals" period="Simulated decisions" />

{#await data.board}
  <p class="note" role="status">CFOcus is checking the forecast and preparing proposals. This can take a few seconds…</p>
  <div class="proposal-grid" aria-hidden="true">
    {#each [0, 1] as placeholder (placeholder)}
      <div class="panel"><span class="skeleton skeleton-line" style:width="40%"></span><span class="skeleton skeleton-line wide"></span><span class="skeleton skeleton-block"></span></div>
    {/each}
  </div>
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
    <DepositComparison proposals={board.proposals} />
    <div class="proposal-grid">
      {#each board.proposals as proposal, index (proposal.id)}
        <article class="panel proposal enter" style:--i={index}>
          <div class="panel-head"><p class="eyebrow">{categoryLabels[proposal.kind]}</p><span class="status">{statusLabels[proposal.status]}</span></div>
          <h2>{proposal.title}</h2><strong class="amount"><AnimatedNumber value={proposal.amount} format={euro} /></strong>
          <p class="badges">
            {#if proposal.requires_approval}<span class="tag">Needs your approval</span>{/if}
            {#if proposal.execution_mode === 'simulated'}<span class="tag estimate">Simulation · no real money moves</span>{/if}
          </p>
          {#if proposal.term_days !== null || proposal.annual_rate_pct !== null}
            <ul class="facts">
              {#if proposal.term_days !== null}<li><span>Term</span><b>{proposal.term_days} days</b></li>{/if}
              {#if proposal.annual_rate_pct !== null}<li><span>Rate (illustrative)</span><b>{proposal.annual_rate_pct.toFixed(1)} % a year</b></li>{/if}
              {#if proposal.interest_eur !== null}<li><span>Interest (illustrative)</span><b>≈ {euro(proposal.interest_eur)}</b></li>{/if}
              {#if proposal.min_amount !== null}<li><span>Offer range</span><b>{euro(proposal.min_amount)} – {euro(proposal.amount)}</b></li>{/if}
            </ul>
          {/if}
          <AmountWaterfall {proposal} startBalance={board.start_balance} />
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
            <p class="decision">{statusLabels[proposal.status]}{#if proposal.decided_at}{' '}on {dateLabel(proposal.decided_at)}{/if} · Simulation recorded</p>
          {/if}
        </article>
      {:else}
        <p class="note">No proposals right now: the forecast shows no spare cash to place and no cash gap to cover.</p>
      {/each}
    </div>
    {#if board.notification_draft}
      <details class="panel">
        <summary>Message drafted by CFOcus</summary>
        <h3>{board.notification_draft.subject}</h3>
        <p class="draft">{board.notification_draft.body}</p>
      </details>
    {/if}
  {/if}
{/await}
<p class="minor" role="status">{notice}</p>

{#await data.activity then activity}
  <section class="panel activity" aria-labelledby="activity-title">
    <h2 id="activity-title">Your approved actions</h2>
    {#if activity.transactions.length}
      <div class="scroll">
        <table>
          <thead><tr><th scope="col">Action</th><th scope="col">Reference</th><th scope="col">Approved</th><th scope="col">Amount</th></tr></thead>
          <tbody>
            {#each activity.transactions as transaction (transaction.id)}
              <tr><th scope="row">{transaction.description}</th><td>{reference(transaction.id)}</td><td>{dateTime(transaction.created_at)}</td><td>{euro(transaction.amount)}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="note">All actions are simulated. Nothing was sent to a real bank.</p>
    {:else}
      <p class="note">You have not approved anything yet.</p>
    {/if}

    <h2 class="activity-sub">Notifications</h2>
    {#each activity.notifications as notification (notification.id)}
      <details class="notification">
        <summary><span>{notification.subject}</span><span class="minor">{deliveryLabels[notification.status]} · {dateTime(notification.created_at)}</span></summary>
        <p class="minor">To: {notification.recipient}</p>
        <p class="draft">{notification.body}</p>
      </details>
    {:else}
      <p class="note">No notifications yet. You get one for every approval.</p>
    {/each}
  </section>
{/await}
