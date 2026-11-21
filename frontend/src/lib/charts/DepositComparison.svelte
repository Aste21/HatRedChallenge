<script lang="ts">
  import { euro, type Proposal } from '../forecast';

  let { proposals }: { proposals: Proposal[] } = $props();

  // One bar per product family: the term the agent recommends in that family.
  let offers = $derived(proposals
    .filter((proposal) => proposal.kind !== 'credit_line' && proposal.is_recommended_term && proposal.interest_eur !== null && proposal.term_days !== null)
    .sort((first, second) => (first.family_rank ?? 0) - (second.family_rank ?? 0)));
  let best = $derived(offers.reduce<Proposal | null>((top, offer) => (top === null || (offer.interest_eur ?? 0) > (top.interest_eur ?? 0) ? offer : top), null));
  let largest = $derived(Math.max(...offers.map((offer) => offer.interest_eur ?? 0), 1));
  const label = (offer: Proposal) => `${offer.family_name ?? 'Offer'}, ${offer.term_days} days`;
</script>

{#if offers.length > 1 && best}
  <figure class="panel chart-figure comparison enter">
    <h2>Compare the suggested options</h2>
    <p class="chart-desc">They use the same cash, so you can choose one. The {label(best)} earns the most ({euro(best.interest_eur ?? 0)}), but compare how long your money is locked.</p>
    <ul class="spending" aria-label={'Illustrative return: ' + offers.map((offer) => `${label(offer)} ${euro(offer.interest_eur ?? 0)}`).join(', ')}>
      {#each offers as offer, index (offer.id)}
        <li style:--i={index}>
          <span class="spending-name">{label(offer)} · {offer.annual_rate_pct?.toFixed(2)} %</span>
          <span class="spending-track" aria-hidden="true"><span style:width="{((offer.interest_eur ?? 0) / largest) * 100}%" style:background="var(--chart-in)"></span></span>
          <span class="spending-value"><b>≈ {euro(offer.interest_eur ?? 0)}</b> <span class="minor">on {euro(offer.amount)}</span></span>
        </li>
      {/each}
    </ul>
    <p class="minor">Illustrative demo rates, not real quotes. Gross return before any fees or taxes.</p>
  </figure>
{/if}
