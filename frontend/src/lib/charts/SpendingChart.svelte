<script lang="ts">
  import { money, spending } from '../ledger';

  const total = spending.reduce((sum, row) => sum + row.cents, 0);
  const largest = spending[0];
  const share = (cents: number) => new Intl.NumberFormat('en-IE', { style: 'percent', maximumFractionDigits: 0 }).format(cents / total);
  const staffAndGoods = spending.filter((row) => ['Staff salaries', 'Food supplies', 'Wine & drinks', 'Fresh produce'].includes(row.name))
    .reduce((sum, row) => sum + row.cents, 0);
</script>

<figure class="chart-figure">
  <h2>Where the money goes</h2>
  <p class="chart-desc">{largest.name} is your largest cost ({share(largest.cents)} of all payments). Staff and ingredients together make up {share(staffAndGoods)}.</p>
  <ul class="spending" aria-label={'Money out in 2025 by category: ' + spending.map((row) => `${row.name} ${money(row.cents)}`).join(', ')}>
    {#each spending as row, index (row.name)}
      <li style:--i={index}>
        <span class="spending-name">{row.name}</span>
        <span class="spending-track" aria-hidden="true"><span style:width="{(row.cents / largest.cents) * 100}%" class:fx={row.name.includes('CHF')}></span></span>
        <span class="spending-value"><b>{money(row.cents)}</b> <span class="minor">{share(row.cents)}</span></span>
      </li>
    {/each}
  </ul>
  <p class="minor">All payments out of your account in 2025, total {money(total)}. The Zurich payout is paid in Swiss francs and converted at the rate on each transfer, so its euro cost moves with the exchange rate.</p>
</figure>
