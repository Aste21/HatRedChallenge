<script lang="ts">
  import { money, useLedger } from '../ledger';
  import { buildChartData, type ChartSpec } from './custom';
  import { euroCompact, linear, niceTicks } from './scale';

  let { spec, heading = 'h2' }: { spec: ChartSpec; heading?: 'h2' | 'h3' } = $props();
  const ledger = useLedger();

  let data = $derived(buildChartData(ledger, spec));
  let width = $state(0);
  let selected = $state<number | null>(null);
  let hiddenSeries = $state<string[]>([]);
  let shownSeries = $derived(data.series.filter((series) => !hiddenSeries.includes(series.metric)));
  let count = $derived(data.labels.length);

  // Time series
  const margin = { top: 12, right: 10, bottom: 26, left: 54 };
  let height = $derived(width < 500 ? 210 : 250);
  let ticks = $derived(niceTicks(shownSeries.flatMap((series) => series.values).map((cents) => cents / 100), width < 500 ? 4 : 5));
  let y = $derived(linear(ticks[0] * 100, ticks[ticks.length - 1] * 100, height - margin.bottom, margin.top));
  let slot = $derived((width - margin.left - margin.right) / Math.max(count, 1));
  let bar = $derived(Math.max(Math.min((slot * 0.8) / Math.max(shownSeries.length, 1), 22), 1));
  let labelEvery = $derived(Math.max(1, Math.ceil(count / Math.max(1, Math.floor((width - margin.left) / 52)))));
  const left = (index: number) => margin.left + index * slot + slot / 2;
  const linePath = (values: number[]) => values.map((value, index) => `${index ? 'L' : 'M'}${left(index)},${y(value)}`).join('');
  const areaPath = (values: number[]) => `${linePath(values)}L${left(values.length - 1)},${y(0)}L${left(0)},${y(0)}Z`;

  // Breakdown
  let largest = $derived(Math.max(...(data.series[0]?.values ?? [0]), 1));
  let total = $derived((data.series[0]?.values ?? []).reduce((sum, value) => sum + value, 0));
  const share = (cents: number) => new Intl.NumberFormat('en-IE', { style: 'percent', maximumFractionDigits: 0 }).format(total ? cents / total : 0);

  let readoutIndex = $derived(selected ?? count - 1);

  function inspect(event: PointerEvent) {
    const box = (event.currentTarget as SVGElement).getBoundingClientRect();
    const index = Math.floor((event.clientX - box.left - margin.left) / slot);
    selected = index >= 0 && index < count ? index : null;
  }
  function onKeydown(event: KeyboardEvent) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const step = event.key === 'ArrowLeft' ? -1 : 1;
    selected = Math.min(Math.max((selected ?? count - 1) + step, 0), count - 1);
  }
  function toggleSeries(metric: string) {
    if (hiddenSeries.includes(metric)) hiddenSeries = hiddenSeries.filter((item) => item !== metric);
    else if (shownSeries.length > 1) hiddenSeries = [...hiddenSeries, metric];
  }
</script>

<figure class="chart-figure custom-chart">
  <svelte:element this={heading} class="custom-chart-title">{spec.title}</svelte:element>
  <p class="chart-desc">{data.coverage}. Figures computed from your bank statement.</p>

  {#if !count}
    <p class="note">There is no bank data for the months this chart asks for.</p>
  {:else if data.kind === 'category'}
    {@const series = data.series[0]}
    <ul class="spending" aria-label={`${series.label}: ` + data.labels.map((label, index) => `${label} ${money(series.values[index])}`).join(', ')}
      onpointerleave={() => selected = null}>
      {#each data.labels as label, index (label)}
        <li style:--i={index} class:dimmed={selected !== null && selected !== index} onpointerover={() => selected = index}>
          <span class="spending-name">{label}</span>
          <span class="spending-track" aria-hidden="true"><span style:width="{(Math.max(series.values[index], 0) / largest) * 100}%" style:background={series.color}></span></span>
          <span class="spending-value"><b>{money(series.values[index])}</b>{#if series.metric !== 'takings_by_weekday'}&nbsp;<span class="minor">{share(series.values[index])}</span>{/if}</span>
        </li>
      {/each}
    </ul>
  {:else}
    {#if data.series.length > 1}
      <div class="series-toggles" role="group" aria-label="Show or hide lines">
        {#each data.series as series (series.metric)}
          <button aria-pressed={!hiddenSeries.includes(series.metric)} onclick={() => toggleSeries(series.metric)}
            disabled={!hiddenSeries.includes(series.metric) && shownSeries.length === 1}>
            <i style:background={series.color} aria-hidden="true"></i>{series.label}
          </button>
        {/each}
      </div>
    {:else}
      <p class="legend" aria-hidden="true"><span><i style:background={data.series[0].color}></i>{data.series[0].label}</span></p>
    {/if}
    <!-- Arrow keys move the readout, so the chart works without a mouse; the table below lists all values. -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
    <div class="chart-box" bind:clientWidth={width} tabindex="0" role="group"
      aria-label="{spec.title}. Use the left and right arrow keys to read the values." onkeydown={onKeydown}>
      {#if width > 0}
        <svg {width} {height} role="img" aria-label="{spec.chart_type} chart of {shownSeries.map((series) => series.label).join(', ')}"
          onpointermove={inspect} onpointerleave={() => selected = null}>
          {#each ticks as tick (tick)}
            <line class={tick === 0 ? 'zero' : 'grid'} x1={margin.left} x2={width - margin.right} y1={y(tick * 100)} y2={y(tick * 100)} />
            <text x={margin.left - 8} y={y(tick * 100) + 4} text-anchor="end">{euroCompact(tick)}</text>
          {/each}
          {#if selected !== null}
            <line class="guide" x1={left(selected)} x2={left(selected)} y1={margin.top} y2={height - margin.bottom} />
          {/if}
          {#each shownSeries as series, seriesIndex (series.metric)}
            {#if spec.chart_type === 'bar'}
              <g class="chart-reveal">
                {#each series.values as value, index (index)}
                  <rect x={left(index) - (bar * shownSeries.length) / 2 + seriesIndex * bar} y={Math.min(y(value), y(0))}
                    width={Math.max(bar - (bar > 4 ? 1 : 0), 1)} height={Math.max(Math.abs(y(0) - y(value)), 0.5)} rx={bar > 6 ? 2 : 0}
                    style:fill={series.color} opacity={selected === null || selected === index ? 1 : 0.45} />
                {/each}
              </g>
            {:else}
              <g class="chart-reveal">
                {#if spec.chart_type === 'area'}<path d={areaPath(series.values)} style:fill={series.color} opacity=".18" />{/if}
                <path d={linePath(series.values)} fill="none" style:stroke={series.color} stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
                {#if count <= 24}
                  {#each series.values as value, index (index)}
                    <circle cx={left(index)} cy={y(value)} r="3" style:fill={series.color} />
                  {/each}
                {/if}
                {#if selected !== null}
                  <circle cx={left(selected)} cy={y(series.values[selected])} r="5" style:fill={series.color} style:stroke="var(--surface)" stroke-width="2" />
                {/if}
              </g>
            {/if}
          {/each}
          {#each data.labels as label, index (index)}
            {#if index % labelEvery === 0}
              <text x={left(index)} y={height - 7} text-anchor="middle">{label}</text>
            {/if}
          {/each}
        </svg>
      {/if}
    </div>
  {/if}

  {#if count}
    <p class="chart-readout" aria-live="polite">
      {data.longLabels[readoutIndex]}:
      {#each (data.kind === 'time' ? shownSeries : data.series) as series, index (series.metric)}
        {index ? ' · ' : ''}{data.kind === 'time' ? `${series.label} ` : ''}<b class:negative={series.values[readoutIndex] < 0}>{money(series.values[readoutIndex])}</b>
      {/each}
    </p>
    <details class="chart-table">
      <summary>Show the numbers</summary>
      <div class="scroll">
        <table>
          <thead><tr><th scope="col">{data.kind === 'time' ? 'Period' : 'Item'}</th>{#each data.series as series (series.metric)}<th scope="col">{series.label}</th>{/each}</tr></thead>
          <tbody>
            {#each data.longLabels as label, index (index)}
              <tr><th scope="row">{label}</th>{#each data.series as series (series.metric)}<td class:negative={series.values[index] < 0}>{money(series.values[index])}</td>{/each}</tr>
            {/each}
          </tbody>
        </table>
      </div>
    </details>
  {/if}
</figure>
