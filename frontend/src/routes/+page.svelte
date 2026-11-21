<script lang="ts">
  import Heading from '#lib/Heading.svelte';
  import BalanceChart from '#lib/BalanceChart.svelte';
  import { months, december, closing, bills, lowest, scenario, dateLabel, money } from '#lib/ledger.ts';
  import { providePageDetails } from '#lib/chat/page-context.ts';
  import { euro } from '#lib/forecast.ts';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
  let allMonths = $state(false);
  const newest = [...months].reverse();

  function forecastDetails(): string[] {
    const daily = data.forecast?.official.daily;
    if (!daily) {
      return [
        'Chart "Forecast" tab, illustrative January 2026 scenario with scheduled bills only and no receipts:',
        ...[7, 14, 31].map((days) => `after ${days} days (${dateLabel(scenario[days - 1].date)}): ${money(scenario[days - 1].balance)}`)
      ];
    }
    return [
      'Chart "Forecast" tab, forecast from the forecasting service (expected balance, likely range 5th–95th percentile):',
      ...[30, 60, 90].filter((days) => days <= daily.length).map((days) => {
        const day = daily[days - 1];
        return `after ${days} days (${dateLabel(day.date)}): ${euro(day.p50)} (likely ${euro(day.p5)} to ${euro(day.p95)})`;
      })
    ];
  }

  // The chart and the collapsed table hide figures that are not plain text on screen; give them to the assistant.
  providePageDetails(() => [
    'Monthly balances 2025 (money in / money out / closing balance):',
    ...months.map((row) => `${row.name}: ${money(row.income)} / ${money(row.costs)} / ${money(row.balance)}`),
    `Lowest daily balance: ${money(lowest.balance)} on ${dateLabel(lowest.date)}.`,
    ...forecastDetails()
  ].join('\n'));
</script>

<svelte:head><title>Cashflow</title></svelte:head>
<Heading title="Cashflow" period={dateLabel(closing.date, true)} />

<div class="metrics">
  <section><h2>Closing balance</h2><strong>{money(closing.balance)}</strong></section>
  <section><h2>December receipts</h2><strong>{money(december.income)}</strong></section>
  <section><h2>December payments</h2><strong>{money(december.costs)}</strong></section>
</div>

<div class="overview">
  <BalanceChart forecast={data.forecast?.official.daily ?? null} />
  <section class="panel schedule">
    <div class="panel-head"><h2>Scheduled payments</h2><span class="minor">January 2026</span></div>
    <ul>
      {#each bills as bill}
        <li><time datetime={'2026-01-' + String(bill.day).padStart(2,'0')}>Jan {bill.day}</time><span>{bill.name}</span><b>{money(bill.cents)}</b></li>
      {/each}
    </ul>
    <a href="/proposals">Review proposals</a>
  </section>
</div>

<section class="panel">
  <div class="panel-head">
    <h2>Monthly balances</h2>
    <button class="textbtn" aria-expanded={allMonths} onclick={() => allMonths = !allMonths}>
      {allMonths ? 'Show latest months' : 'View all 12 months'}
    </button>
  </div>
  <div class="scroll">
    <table>
      <thead><tr><th scope="col">Month</th><th scope="col">Money in</th><th scope="col">Money out</th><th scope="col">Closing balance</th></tr></thead>
      <tbody>
        {#each (allMonths ? newest : newest.slice(0,3)) as row}
          <tr><th scope="row">{row.name}</th><td>{money(row.income)}</td><td>{money(row.costs)}</td><td class:negative={row.balance<0}>{money(row.balance)}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
  <p class="note">Lowest daily balance in 2025: {money(lowest.balance)} on {dateLabel(lowest.date)}.</p>
</section>
