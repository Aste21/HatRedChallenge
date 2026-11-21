<script lang="ts">
  import { Tween, prefersReducedMotion } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { history, scenario, dateLabel, money } from './ledger';
  import { euroCompact, linear, niceTicks } from './charts/scale';
  import type { ChartMarker, ForecastDay } from './forecast';

  type Row = { date: string; balance: number; low?: number; high?: number; compare?: number };

  let {
    forecast = null,
    compare = null,
    activeLabel = 'Expected balance',
    compareLabel = '',
    buffer = null,
    markers = []
  }: {
    forecast?: ForecastDay[] | null;
    compare?: ForecastDay[] | null;
    activeLabel?: string;
    compareLabel?: string;
    buffer?: number | null;
    markers?: ChartMarker[];
  } = $props();

  const toCents = (euros: number) => Math.round(euros * 100);
  let range = $state('Year');
  let horizonChoice = $state(2);
  let position = $state<number | null>(null);
  let tooltip = $state(false);
  let width = $state(0);

  let horizons = $derived(forecast ? [30, 60, 90] : [7, 14, 31]);
  let horizon = $derived(horizons[horizonChoice]);
  let forecastRows = $derived<Row[]>(forecast
    ? forecast.slice(0, horizon).map((day, index) => ({
        date: day.date, balance: toCents(day.p50), low: toCents(day.p5), high: toCents(day.p95),
        compare: compare?.[index] ? toCents(compare[index].p50) : undefined
      }))
    : scenario.slice(0, horizon));
  let rows = $derived<Row[]>(range === 'Forecast' ? [history[history.length - 1], ...forecastRows] : range === 'Quarter' ? history.slice(-92) : history);
  let showBand = $derived(range === 'Forecast' && forecast !== null);
  let showCompare = $derived(showBand && compare !== null);

  // Values glide when the data changes in place (scenario switch); a new range redraws with a reveal instead.
  let viewKey = $derived(`${range}-${horizon}`);
  let target = $derived(rows.flatMap((r) => [r.balance, r.low ?? r.balance, r.high ?? r.balance, r.compare ?? r.balance]));
  const tween = new Tween<number[]>([], { duration: 300, easing: cubicOut });
  let lastKey = '';
  $effect(() => {
    const instant = viewKey !== lastKey || tween.target.length !== target.length || prefersReducedMotion.current;
    lastKey = viewKey;
    tween.set(target, { duration: instant ? 0 : 300 });
  });
  let values = $derived(tween.current.length === target.length ? tween.current : target);
  const at = (index: number, slot: number) => values[index * 4 + slot];

  let bufferCents = $derived(showBand && buffer !== null ? toCents(buffer) : null);
  let worstIndex = $derived(showBand ? rows.reduce((best, r, i) => i > 0 && (r.low ?? r.balance) < (rows[best].low ?? rows[best].balance) ? i : best, 1) : -1);
  let ticks = $derived(niceTicks([...target, ...(bufferCents === null ? [] : [bufferCents])].map((cents) => cents / 100), width < 500 ? 4 : 6));
  let height = $derived(width < 500 ? 210 : 250);
  const margin = { top: 22, right: 10, bottom: 26, left: 52 };
  let x = $derived(linear(0, rows.length - 1, margin.left, Math.max(width - margin.right, margin.left + 1)));
  let y = $derived(linear(ticks[0] * 100, ticks[ticks.length - 1] * 100, height - margin.bottom, margin.top));
  const line = (slot: number) => rows.map((_, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(at(i, slot)).toFixed(1)).join(' ');
  let path = $derived(line(0));
  let comparePath = $derived(showCompare ? line(3) : '');
  let band = $derived(showBand
    ? line(2) + ' ' + rows.map((_, i) => i).reverse().map((i) => 'L' + x(i).toFixed(1) + ',' + y(at(i, 1)).toFixed(1)).join(' ') + ' Z'
    : '');
  // Markers on the same day share one badge ("1, 3") so they never hide each other.
  let visibleMarkers = $derived.by(() => {
    if (range !== 'Forecast' || !forecast) return [];
    const byIndex = new Map<number, ChartMarker[]>();
    for (const marker of markers) {
      const position = rows.findIndex((r) => r.date >= marker.date);
      if (position > 0) byIndex.set(position, [...(byIndex.get(position) ?? []), marker]);
    }
    return [...byIndex].map(([position, group]) => ({
      index: position, numbers: group.map((marker) => marker.number).join(', '), label: group.map((marker) => marker.label).join('; ')
    }));
  });

  let index = $derived(Math.min(position ?? rows.length - 1, rows.length - 1));
  let active = $derived(rows[index]);
  let tooltipLeft = $derived(Math.min(Math.max(x(index), 90), Math.max(width - 90, 90)));
  const dateFormat = (iso: string) => new Intl.DateTimeFormat('en-GB', { month: 'short', ...(range === 'Year' ? {} : { day: 'numeric' as const }), timeZone: 'UTC' }).format(new Date(iso));

  function setRange(value: string) { position = null; range = value; }
  function inspect(event: PointerEvent) {
    const box = (event.currentTarget as SVGElement).getBoundingClientRect();
    const fraction = (event.clientX - box.left - margin.left) / Math.max(box.width - margin.left - margin.right, 1);
    position = Math.round(Math.min(Math.max(fraction, 0), 1) * (rows.length - 1));
    tooltip = true;
  }
</script>

<section class="panel chart">
  <div class="panel-head"><h2>Balance over time</h2>
    <div class="switches" aria-label="Chart range">{#each ['Year','Quarter','Forecast'] as option (option)}
      <button aria-pressed={range === option} onclick={() => setRange(option)}>{option}</button>
    {/each}</div>
  </div>
  {#if range === 'Forecast'}
    <label class="horizon">Forecast horizon
      <select bind:value={horizonChoice} onchange={() => position = null}>
        {#each horizons as days, choice (days)}<option value={choice}>{days} days</option>{/each}
      </select>
    </label>
  {/if}
  <p class="chart-key">
    <i class:scenario={range === 'Forecast'}></i>{range === 'Forecast' ? (forecast ? activeLabel : 'Fixed-cost scenario') : 'Daily closing balance'}
    {#if showBand}<i class="band"></i>Likely range{/if}
    {#if showCompare}<i class="compare"></i>{compareLabel}{/if}
    {#if bufferCents !== null}<i class="buffer"></i>Cash buffer{/if}
    {#if worstIndex > 0}<i class="worst"></i>Worst case{/if}
    <span>EUR</span>
  </p>
  <div class="chart-box" bind:clientWidth={width}>
    {#if width > 0}
      <svg {width} {height} role="img" aria-label={`${range} balance chart in euros. Latest value ${dateLabel(rows[rows.length - 1].date)}: ${money(rows[rows.length - 1].balance)}.`}
        onpointermove={inspect} onpointerdown={inspect} onpointerleave={() => tooltip = false}>
        <defs><linearGradient id="balance-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#168577" stop-opacity=".19"/><stop offset="1" stop-color="#168577" stop-opacity=".015"/></linearGradient></defs>
        {#each ticks as tick (tick)}
          <line class={tick === 0 ? 'zero' : 'grid'} x1={margin.left} x2={width - margin.right} y1={y(tick * 100)} y2={y(tick * 100)}/>
          <text x={margin.left - 8} y={y(tick * 100) + 4} text-anchor="end">{euroCompact(tick)}</text>
        {/each}
        {#key viewKey}
          <g class="chart-reveal">
            {#if showBand}
              <path d={band} fill="#168577" fill-opacity=".16"/>
            {:else}
              <path d={path + ` L${x(rows.length - 1)},${height - margin.bottom} L${margin.left},${height - margin.bottom} Z`} fill="url(#balance-fill)"/>
            {/if}
            {#if showCompare}<path d={comparePath} fill="none" stroke="var(--chart-out)" stroke-width="2" stroke-dasharray="4 4"/>{/if}
            <path d={path} fill="none" stroke="#117765" stroke-width="2.6" stroke-linejoin="round" stroke-dasharray={range === 'Forecast' ? '6 3' : undefined}/>
          </g>
        {/key}
        {#if bufferCents !== null}
          <line x1={margin.left} x2={width - margin.right} y1={y(bufferCents)} y2={y(bufferCents)} stroke="var(--chart-buffer)" stroke-width="1.6" stroke-dasharray="8 4"/>
          <text class="buffer-label" x={width - margin.right} y={y(bufferCents) - 6} text-anchor="end">Cash buffer {money(bufferCents)}</text>
        {/if}
        {#each visibleMarkers as marker (marker.index)}
          {@const badge = 8 + (marker.numbers.length - 1) * 3.4}
          <line x1={x(marker.index)} x2={x(marker.index)} y1={margin.top} y2={height - margin.bottom} stroke="#7a4a12" stroke-dasharray="2 3"/>
          <rect x={x(marker.index) - badge} y={margin.top - 16} width={badge * 2} height="16" rx="8" fill="#fbf3e6" stroke="#7a4a12"/>
          <text class="strong" x={x(marker.index)} y={margin.top - 4} text-anchor="middle"><title>{marker.label}</title>{marker.numbers}</text>
        {/each}
        {#if worstIndex > 0}
          <circle cx={x(worstIndex)} cy={y(at(worstIndex, 1))} r="5" fill="var(--chart-risk)" stroke="white" stroke-width="2"/>
        {/if}
        <line x1={x(index)} x2={x(index)} y1={y(at(index, 0))} y2={height - margin.bottom} stroke="#356b5d" stroke-dasharray="2 3"/>
        <circle cx={x(index)} cy={y(at(index, 0))} r="4.5" fill="#075e50" stroke="white" stroke-width="2"/>
        {#each [0, .25, .5, .75, 1] as fraction (fraction)}
          {@const n = Math.round(fraction * (rows.length - 1))}
          <text x={x(n)} y={height - 6} text-anchor={fraction === 1 ? 'end' : fraction === 0 ? 'start' : 'middle'}>{dateFormat(rows[n].date)}</text>
        {/each}
      </svg>
      {#if tooltip}
        <div class="chart-tooltip" style:left="{tooltipLeft}px" style:top="{margin.top + 4}px" style:transform="translateX(-50%)">
          <span class="minor">{dateLabel(active.date)}</span>
          <b>{money(active.balance)}</b>
          {#if showBand && active.low !== undefined && active.high !== undefined}<span class="minor">likely {money(active.low)} to {money(active.high)}</span>{/if}
          {#if showCompare && active.compare !== undefined}<br/><span class="minor">{compareLabel}: {money(active.compare)}</span>{/if}
        </div>
      {/if}
    {/if}
  </div>
  <div class="readout"><label for="day">Inspect date</label><input id="day" type="range" min="0" max={rows.length-1} value={index}
    oninput={(e) => position = +e.currentTarget.value} onfocus={() => tooltip = true} onblur={() => tooltip = false}
    onkeydown={(e) => { if (e.key === 'Escape') tooltip = false; }}
    aria-valuetext={dateLabel(active.date) + ', ' + money(active.balance)}/><output>{dateLabel(active.date)} · <b>{money(active.balance)}</b>{#if showBand && active.low !== undefined && active.high !== undefined}{' '}<span class="minor">(likely {money(active.low)} to {money(active.high)})</span>{/if}</output></div>
  {#if range === 'Forecast'}
    {#if forecast}
      <p class="note">Forecast from your bank history: the dashed line is the expected balance, the shaded band covers 90 % of 4,000 simulated futures. Scheduled payments are included.{#if worstIndex > 0}{' '}In a bad case the balance is lowest on {dateLabel(rows[worstIndex].date)}: {money(rows[worstIndex].low ?? rows[worstIndex].balance)}.{/if}{#if visibleMarkers.length}{' '}Numbered markers show when news changes your cash flow.{/if}</p>
    {:else}
      <p class="note">The forecast service is not connected. Showing an illustrative January 2026 scenario using scheduled bills and zero receipts. Variable costs are excluded.</p>
    {/if}
  {/if}
</section>
