<script lang="ts">
  import { euro, type Proposal } from '../forecast';

  let { proposal, startBalance }: { proposal: Proposal; startBalance: number } = $props();

  type Step = { label: string; from: number; to: number; tone: 'in' | 'risk' | 'buffer' | 'result'; value: number };

  // Each bar floats from where the previous step left the balance, so the proposal's arithmetic reads left to right.
  let steps = $derived.by<Step[]>(() => {
    const lowest = proposal.lowest_balance;
    if (lowest === null) return [];
    const start: Step = { label: 'Balance today', from: 0, to: startBalance, tone: 'in', value: startBalance };
    const dip: Step = { label: 'Possible dip (bad case)', from: startBalance, to: lowest, tone: 'risk', value: lowest - startBalance };
    if (proposal.kind === 'credit_line') {
      const covered = lowest + proposal.amount;
      return [start, dip,
        { label: 'Credit line', from: lowest, to: covered, tone: 'in', value: proposal.amount },
        { label: 'Lowest balance with it', from: 0, to: covered, tone: 'result', value: covered }];
    }
    if (proposal.buffer_eur === null || proposal.safe_amount === null) return [];
    return [start, dip,
      { label: 'Cash buffer you keep', from: lowest, to: lowest - proposal.buffer_eur, tone: 'buffer', value: -proposal.buffer_eur },
      { label: 'Safe to set aside', from: 0, to: proposal.safe_amount, tone: 'result', value: proposal.safe_amount }];
  });
  let low = $derived(Math.min(0, ...steps.flatMap((step) => [step.from, step.to])));
  let high = $derived(Math.max(...steps.flatMap((step) => [step.from, step.to]), 1));
  const position = (value: number) => ((value - low) / (high - low)) * 100;
</script>

{#if steps.length}
  <figure class="waterfall" aria-label={'How this amount is calculated: ' + steps.map((step) => `${step.label} ${euro(step.value)}`).join(', ')}>
    <figcaption class="eyebrow">How we got to this amount</figcaption>
    {#each steps as step, index (step.label)}
      <div class="waterfall-row" style:--i={index}>
        <span>{step.label}</span>
        <span class="waterfall-track" aria-hidden="true">
          {#if low < 0}<i class="waterfall-zero" style:left="{position(0)}%"></i>{/if}
          <span class="waterfall-bar {step.tone}" style:left="{position(Math.min(step.from, step.to))}%" style:width="{Math.max(Math.abs(position(step.to) - position(step.from)), 0.6)}%"></span>
        </span>
        <b class:negative={step.value < 0}>{step.value > 0 && index > 0 && step.tone !== 'result' ? '+' : ''}{euro(step.value)}</b>
      </div>
    {/each}
    {#if proposal.safe_amount !== null && proposal.amount < proposal.safe_amount}
      <p class="minor">The offer allows at most {euro(proposal.amount)}, so the proposal is capped there.</p>
    {/if}
  </figure>
{/if}
