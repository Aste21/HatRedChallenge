<script lang="ts">
  import { history, scenario, dateLabel, money } from './ledger';
  let range = $state('Year');
  let horizon = $state(31);
  let position = $state<number | null>(null);
  let rows = $derived(range === 'Forecast' ? [history[history.length - 1], ...scenario.slice(0, horizon)] : range === 'Quarter' ? history.slice(-92) : history);
  let min = $derived(Math.min(0, Math.floor(Math.min(...rows.map(r => r.balance)) / 1000000) * 1000000));
  let max = $derived(Math.max(1000000, Math.ceil(Math.max(...rows.map(r => r.balance)) / 1000000) * 1000000));
  const left = 50, right = 695, top = 17, bottom = 188;
  const x = (i: number) => left + i / (rows.length - 1) * (right - left);
  const y = (value: number) => bottom - (value - min) / (max - min) * (bottom - top);
  let ticks = $derived(Array.from({length: (max - min) / 1000000 + 1}, (_, i) => min + i * 1000000));
  let path = $derived(rows.map((r, i) => (i ? 'L' : 'M') + x(i).toFixed(2) + ',' + y(r.balance).toFixed(2)).join(' '));
  let index = $derived(Math.min(position ?? rows.length - 1, rows.length - 1));
  let active = $derived(rows[index]);
  function setRange(value: string) { position = null; range = value; }
</script>
<section class="panel chart">
  <div class="panel-head"><h2>Balance over time</h2>
    <div class="switches" aria-label="Chart range">{#each ['Year','Quarter','Forecast'] as option}
      <button aria-pressed={range === option} onclick={() => setRange(option)}>{option}</button>
    {/each}</div>
  </div>
  {#if range === 'Forecast'}
    <label class="horizon">Forecast horizon
      <select bind:value={horizon} onchange={() => position = null}>
        {#each [7, 14, 31] as days}<option value={days}>{days} days</option>{/each}
      </select>
    </label>
  {/if}
  <p class="chart-key"><i class:scenario={range === 'Forecast'}></i>{range === 'Forecast' ? 'Fixed-cost scenario' : 'Daily closing balance'} <span>EUR</span></p>
  <div class="plot">
    <svg viewBox="0 0 712 221" role="img" aria-label={range + ' balance chart in euros'}>
      <defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#168577" stop-opacity=".19"/><stop offset="1" stop-color="#168577" stop-opacity=".015"/></linearGradient></defs>
      {#each ticks as tick}<line x1={left} x2={right} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? '#a7b3aa' : '#e1e6df'} stroke-dasharray={tick === 0 ? undefined : '3 4'}/><text x={left-8} y={y(tick)+4} text-anchor="end">{tick === 0 ? '€0' : '€' + tick/100000 + 'k'}</text>{/each}
      <path d={path + ' L' + right + ',' + bottom + ' L' + left + ',' + bottom + ' Z'} fill="url(#fill)"/>
      <path d={path} fill="none" stroke="#117765" stroke-width="2.6" stroke-linejoin="round" stroke-dasharray={range === 'Forecast' ? '6 3' : undefined}/>
      <line x1={x(index)} x2={x(index)} y1={y(active.balance)} y2={bottom} stroke="#356b5d" stroke-dasharray="2 3"/>
      <circle cx={x(index)} cy={y(active.balance)} r="4.5" fill="#075e50" stroke="white" stroke-width="2"/>
      {#each [0, .25, .5, .75, 1] as fraction}
        {@const n = Math.round(fraction * (rows.length-1))}
        <text x={x(n)} y="214" text-anchor={fraction===1 ? 'end' : fraction===0 ? 'start' : 'middle'}>{new Intl.DateTimeFormat('en-GB',{month:'short', ...(range === 'Year' ? {} : {day:'numeric' as const}),timeZone:'UTC'}).format(new Date(rows[n].date))}</text>
      {/each}
    </svg>
  </div>
  <div class="readout"><label for="day">Inspect date</label><input id="day" type="range" min="0" max={rows.length-1} value={index} oninput={(e) => position = +e.currentTarget.value} aria-valuetext={dateLabel(active.date) + ', ' + money(active.balance)}/><output>{dateLabel(active.date)} · <b>{money(active.balance)}</b></output></div>
  {#if range === 'Forecast'}<p class="note">Illustrative January 2026 scenario using scheduled bills and zero receipts. Variable costs are excluded.</p>{/if}
</section>
