<script lang="ts">
  import { history, scenario, dateLabel, money } from './ledger';
  import type { ForecastDay } from './forecast';

  type Row = { date: string; balance: number; low?: number; high?: number };

  let { forecast = null }: { forecast?: ForecastDay[] | null } = $props();

  const toCents = (euros: number) => Math.round(euros * 100);
  let range = $state('Year');
  let horizonChoice = $state(2);
  let position = $state<number | null>(null);
  let horizons = $derived(forecast ? [30, 60, 90] : [7, 14, 31]);
  let horizon = $derived(horizons[horizonChoice]);
  let forecastRows = $derived<Row[]>(forecast
    ? forecast.slice(0, horizon).map((day) => ({ date: day.date, balance: toCents(day.p50), low: toCents(day.p5), high: toCents(day.p95) }))
    : scenario.slice(0, horizon));
  let rows = $derived<Row[]>(range === 'Forecast' ? [history[history.length - 1], ...forecastRows] : range === 'Quarter' ? history.slice(-92) : history);
  let showBand = $derived(range === 'Forecast' && forecast !== null);
  let values = $derived(rows.flatMap((r) => [r.low ?? r.balance, r.high ?? r.balance]));
  let min = $derived(Math.min(0, Math.floor(Math.min(...values) / 1000000) * 1000000));
  let max = $derived(Math.max(1000000, Math.ceil(Math.max(...values) / 1000000) * 1000000));
  const left = 50, right = 695, top = 17, bottom = 188;
  const x = (i: number) => left + i / (rows.length - 1) * (right - left);
  const y = (value: number) => bottom - (value - min) / (max - min) * (bottom - top);
  let ticks = $derived(Array.from({length: (max - min) / 1000000 + 1}, (_, i) => min + i * 1000000));
  let path = $derived(rows.map((r, i) => (i ? 'L' : 'M') + x(i).toFixed(2) + ',' + y(r.balance).toFixed(2)).join(' '));
  let band = $derived(showBand
    ? rows.map((r, i) => (i ? 'L' : 'M') + x(i).toFixed(2) + ',' + y(r.high ?? r.balance).toFixed(2)).join(' ') + ' ' +
      rows.map((r, i) => ({ r, i })).reverse().map(({ r, i }) => 'L' + x(i).toFixed(2) + ',' + y(r.low ?? r.balance).toFixed(2)).join(' ') + ' Z'
    : '');
  let index = $derived(Math.min(position ?? rows.length - 1, rows.length - 1));
  let active = $derived(rows[index]);
  function setRange(value: string) { position = null; range = value; }
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
  <p class="chart-key"><i class:scenario={range === 'Forecast'}></i>{range === 'Forecast' ? (forecast ? 'Expected balance' : 'Fixed-cost scenario') : 'Daily closing balance'}{#if showBand}<i class="band"></i>Likely range{/if} <span>EUR</span></p>
  <div class="plot">
    <svg viewBox="0 0 712 221" role="img" aria-label={range + ' balance chart in euros'}>
      <defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#168577" stop-opacity=".19"/><stop offset="1" stop-color="#168577" stop-opacity=".015"/></linearGradient></defs>
      {#each ticks as tick (tick)}<line x1={left} x2={right} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? '#a7b3aa' : '#e1e6df'} stroke-dasharray={tick === 0 ? undefined : '3 4'}/><text x={left-8} y={y(tick)+4} text-anchor="end">{tick === 0 ? '€0' : '€' + tick/100000 + 'k'}</text>{/each}
      {#if showBand}
        <path d={band} fill="#168577" fill-opacity=".16"/>
      {:else}
        <path d={path + ' L' + right + ',' + bottom + ' L' + left + ',' + bottom + ' Z'} fill="url(#fill)"/>
      {/if}
      <path d={path} fill="none" stroke="#117765" stroke-width="2.6" stroke-linejoin="round" stroke-dasharray={range === 'Forecast' ? '6 3' : undefined}/>
      <line x1={x(index)} x2={x(index)} y1={y(active.balance)} y2={bottom} stroke="#356b5d" stroke-dasharray="2 3"/>
      <circle cx={x(index)} cy={y(active.balance)} r="4.5" fill="#075e50" stroke="white" stroke-width="2"/>
      {#each [0, .25, .5, .75, 1] as fraction (fraction)}
        {@const n = Math.round(fraction * (rows.length-1))}
        <text x={x(n)} y="214" text-anchor={fraction===1 ? 'end' : fraction===0 ? 'start' : 'middle'}>{new Intl.DateTimeFormat('en-GB',{month:'short', ...(range === 'Year' ? {} : {day:'numeric' as const}),timeZone:'UTC'}).format(new Date(rows[n].date))}</text>
      {/each}
    </svg>
  </div>
  <div class="readout"><label for="day">Inspect date</label><input id="day" type="range" min="0" max={rows.length-1} value={index} oninput={(e) => position = +e.currentTarget.value} aria-valuetext={dateLabel(active.date) + ', ' + money(active.balance)}/><output>{dateLabel(active.date)} · <b>{money(active.balance)}</b>{#if showBand && active.low !== undefined && active.high !== undefined} <span class="minor">(likely {money(active.low)} to {money(active.high)})</span>{/if}</output></div>
  {#if range === 'Forecast'}
    {#if forecast}
      <p class="note">Forecast from your bank history: the dashed line is the expected balance, the shaded band covers 90 % of 4,000 simulated futures. Scheduled payments are included.</p>
    {:else}
      <p class="note">The forecast service is not connected. Showing an illustrative January 2026 scenario using scheduled bills and zero receipts. Variable costs are excluded.</p>
    {/if}
  {/if}
</section>
