<script lang="ts">
  import { money, useLedger } from '../ledger';
  import { euroCompact, linear, niceTicks } from './scale';
  const { months } = useLedger();

  let width = $state(0);
  let selected = $state<number | null>(null);

  const rows = months.map((month) => ({ ...month, net: month.income - month.costs }));
  const worst = rows.reduce((low, row) => (row.net < low.net ? row : low));
  let ticks = $derived(niceTicks(rows.flatMap((row) => [row.income, row.costs, row.net]).map((cents) => cents / 100), width < 500 ? 4 : 5));
  let height = $derived(width < 500 ? 200 : 230);
  const margin = { top: 12, right: 8, bottom: 24, left: 50 };
  let slot = $derived((width - margin.left - margin.right) / rows.length);
  let bar = $derived(Math.max(Math.min(slot * 0.32, 18), 3));
  let y = $derived(linear(ticks[0] * 100, ticks[ticks.length - 1] * 100, height - margin.bottom, margin.top));
  const left = (index: number) => margin.left + index * slot + slot / 2;
  let shown = $derived(rows[selected ?? rows.length - 1]);

  function inspect(event: PointerEvent) {
    const box = (event.currentTarget as SVGElement).getBoundingClientRect();
    const index = Math.floor((event.clientX - box.left - margin.left) / slot);
    selected = index >= 0 && index < rows.length ? index : null;
  }
</script>

<figure class="chart-figure">
  <h2>Money in and out per month</h2>
  <p class="chart-desc">Your weakest month was {worst.name}: {money(worst.net)} net, because receipts stopped while fixed costs continued.</p>
  <p class="legend" aria-hidden="true"><span><i style:background="var(--chart-in)"></i>Money in</span><span><i style:background="var(--chart-out)"></i>Money out</span><span><i style:background="var(--fg)" style:border-radius="50%"></i>Net result</span></p>
  <div class="chart-box" bind:clientWidth={width}>
    {#if width > 0}
      <svg {width} {height} role="img" aria-label="Bar chart of money in and money out for each month of 2025, with the net result. The table below lists all values."
        onpointermove={inspect} onpointerleave={() => selected = null}>
        {#each ticks as tick (tick)}
          <line class={tick === 0 ? 'zero' : 'grid'} x1={margin.left} x2={width - margin.right} y1={y(tick * 100)} y2={y(tick * 100)}/>
          <text x={margin.left - 8} y={y(tick * 100) + 4} text-anchor="end">{euroCompact(tick)}</text>
        {/each}
        {#each rows as row, index (row.name)}
          <g class="enter" style:--i={index} opacity={selected === null || selected === index ? 1 : .45}>
            <rect x={left(index) - bar - 1} y={y(row.income)} width={bar} height={Math.max(y(0) - y(row.income), 0)} rx="2" style:fill="var(--chart-in)"/>
            <rect x={left(index) + 1} y={y(row.costs)} width={bar} height={Math.max(y(0) - y(row.costs), 0)} rx="2" style:fill="var(--chart-out)"/>
            <circle cx={left(index)} cy={y(row.net)} r="4" style:fill="var(--fg)" style:stroke="var(--surface)" stroke-width="1.5"/>
            <text x={left(index)} y={height - 6} text-anchor="middle">{width < 500 ? row.name.slice(0, 1) : row.name.slice(0, 3)}</text>
          </g>
        {/each}
      </svg>
    {/if}
  </div>
  <p class="chart-readout">{shown.name}: in <b>{money(shown.income)}</b> · out <b>{money(shown.costs)}</b> · net <b class:negative={shown.net < 0}>{money(shown.net)}</b></p>
</figure>
