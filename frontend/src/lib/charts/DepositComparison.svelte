<script lang="ts">
  import { euro, type Proposal } from '../forecast';

  let { proposals }: { proposals: Proposal[] } = $props();

  let offers = $derived(proposals
    .filter((proposal) => proposal.kind === 'fixed_term_deposit' && proposal.status === 'awaiting_approval' && proposal.interest_eur !== null && proposal.term_days !== null)
    .sort((first, second) => (first.term_days ?? 0) - (second.term_days ?? 0)));
  let best = $derived(offers.reduce<Proposal | null>((top, offer) => (top === null || (offer.interest_eur ?? 0) > (top.interest_eur ?? 0) ? offer : top), null));
  let largest = $derived(Math.max(...offers.map((offer) => offer.interest_eur ?? 0), 1));
</script>

{#if offers.length > 1 && best}
  <figure class="panel chart-figure comparison enter">
    <h2>Compare the deposit offers</h2>
    <p class="chart-desc">They use the same cash, so you can choose one. The {best.term_days}-day deposit earns the most interest ({euro(best.interest_eur ?? 0)}), but your money is locked for longer.</p>
    <ul class="spending" aria-label={'Illustrative interest: ' + offers.map((offer) => `${offer.term_days} days ${euro(offer.interest_eur ?? 0)}`).join(', ')}>
      {#each offers as offer, index (offer.id)}
        <li style:--i={index}>
          <span class="spending-name">{offer.term_days} days · {offer.annual_rate_pct?.toFixed(1)} %</span>
          <span class="spending-track" aria-hidden="true"><span style:width="{((offer.interest_eur ?? 0) / largest) * 100}%" style:background="var(--chart-in)"></span></span>
          <span class="spending-value"><b>≈ {euro(offer.interest_eur ?? 0)}</b> <span class="minor">on {euro(offer.amount)}</span></span>
        </li>
      {/each}
    </ul>
    <p class="minor">Illustrative demo rates, not real quotes.</p>
  </figure>
{/if}
