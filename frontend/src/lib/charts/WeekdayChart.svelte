<script lang="ts">
  import { money, useLedger } from '../ledger';
  import { euroWhole, linear, niceTicks } from './scale';
  const { weekdayTakings } = useLedger();

  let width = $state(0);

  // Daily debit-card settlements per weekday (credit-card payouts arrive in batches and would distort the pattern).
  const names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const rows = names.map((name, weekday) => ({ name, average: weekdayTakings[weekday] }));
  const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length;
  const weekend = mean(weekdayTakings.slice(4));
  const midweek = mean(weekdayTakings.slice(0, 4));
  const uplift = Math.round((weekend / midweek - 1) * 100);
  const ticks = niceTicks(rows.map((row) => row.average / 100), 4);
  let height = $derived(width < 500 ? 190 : 210);
  const margin = { top: 22, right: 4, bottom: 24, left: 4 };
  let slot = $derived((width - margin.left - margin.right) / rows.length);
  let y = $derived(linear(0, ticks[ticks.length - 1] * 100, height - margin.bottom, margin.top));
</script>

<figure class="chart-figure">
  <h2>Average takings by weekday</h2>
  <p class="chart-desc">Friday to Sunday bring about {uplift} % more than Monday to Thursday ({money(weekend)} vs {money(midweek)} a day).</p>
  <div class="chart-box" bind:clientWidth={width}>
    {#if width > 0}
      <svg {width} {height} role="img" aria-label={'Average receipts per open day: ' + rows.map((row) => `${row.name} ${money(row.average)}`).join(', ')}>
        <line class="zero" x1={margin.left} x2={width - margin.right} y1={y(0)} y2={y(0)}/>
        {#each rows as row, index (row.name)}
          {@const barWidth = Math.min(slot * 0.62, 56)}
          {@const center = margin.left + index * slot + slot / 2}
          <g class="enter" style:--i={index}>
            <rect x={center - barWidth / 2} y={y(row.average)} width={barWidth} height={Math.max(y(0) - y(row.average), 0)} rx="3"
              style:fill={index >= 4 ? 'var(--chart-in)' : 'var(--chart-in-soft)'}/>
            <text x={center} y={y(row.average) - 6} text-anchor="middle" class:strong={index >= 4}>{euroWhole(row.average / 100)}</text>
            <text x={center} y={height - 6} text-anchor="middle">{width < 420 ? row.name.slice(0, 2) : row.name.slice(0, 3)}</text>
          </g>
        {/each}
      </svg>
    {/if}
  </div>
  <p class="minor">Daily debit-card settlements from your 2025 statement; closed days are left out. Credit-card payouts arrive in batches twice a week, so they are not included.</p>
</figure>
