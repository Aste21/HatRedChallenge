<script lang="ts">
  import { history, lowest, money } from '../ledger';
  import { weekdayDate } from './scale';

  let width = $state(0);
  let selected = $state(history.indexOf(lowest));

  // Six balance bands around €0, the meaningful midpoint (overdraft vs. money in the account).
  const bands = [
    { below: -1500000, color: '#a8382f', label: 'below −€15k' },
    { below: -500000, color: '#d9877d', label: '−€15k to −€5k' },
    { below: 0, color: '#f2cbc5', label: '−€5k to €0' },
    { below: 1000000, color: '#cfe8e1', label: '€0 to €10k' },
    { below: 2000000, color: '#7fbfae', label: '€10k to €20k' },
    { below: Infinity, color: '#2f7f6d', label: 'above €20k' }
  ];
  const colorOf = (cents: number) => bands.find((band) => cents < band.below)!.color;

  const firstWeekday = (new Date(history[0].date).getUTCDay() + 6) % 7;
  const cells = history.map((day, index) => ({ ...day, column: Math.floor((index + firstWeekday) / 7), row: (index + firstWeekday) % 7 }));
  const columns = cells[cells.length - 1].column + 1;
  const monthStarts = cells.filter((cell) => cell.date.endsWith('-01'));
  const overdraftDays = history.filter((day) => day.balance < 0).length;

  const labelWidth = 30;
  let cell = $derived(Math.max(10, Math.min(18, Math.floor((width - labelWidth) / columns))));
  let svgWidth = $derived(labelWidth + columns * cell);
  let day = $derived(cells[selected]);

</script>

<figure class="chart-figure">
  <h2>Your year at a glance</h2>
  <p class="chart-desc">Each square is one day of 2025, colored by the closing balance. The account was overdrawn on {overdraftDays} days, mostly after the June holiday.</p>
  <div class="chart-box calendar" bind:clientWidth={width}>
    {#if width > 0}
      <svg width={svgWidth} height={20 + 7 * cell} role="img"
        aria-label={`Calendar of daily balances in 2025. Overdrawn on ${overdraftDays} days; lowest ${money(lowest.balance)}. Use the day slider below to read single days.`}>
        {#each monthStarts as start (start.date)}
          <text x={labelWidth + start.column * cell} y="12">{new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' }).format(new Date(start.date))}</text>
        {/each}
        {#each ['Mon', '', 'Wed', '', 'Fri', '', 'Sun'] as label, row (row)}
          {#if label}<text x="0" y={20 + row * cell + cell * 0.72}>{label}</text>{/if}
        {/each}
        {#each cells as cell_, index (cell_.date)}
          <rect x={labelWidth + cell_.column * cell} y={20 + cell_.row * cell} width={cell - 2} height={cell - 2} rx="2"
            fill={colorOf(cell_.balance)} stroke={index === selected ? '#202f32' : 'none'} stroke-width="2"
            onpointerenter={() => selected = index} role="presentation"/>
        {/each}
      </svg>
    {/if}
  </div>
  <div class="readout"><label for="calendar-day">Inspect day</label><input id="calendar-day" type="range" min="0" max={cells.length - 1} bind:value={selected}
    aria-valuetext={`${weekdayDate(day.date)}, balance ${money(day.balance)}`}/></div>
  <p class="chart-readout">{weekdayDate(day.date)} · balance <b class:negative={day.balance < 0}>{money(day.balance)}</b> · in {money(day.income)} · out {money(day.costs)}</p>
  <p class="legend">{#each bands as band (band.label)}<span><i style:background={band.color}></i>{band.label}</span>{/each}</p>
</figure>
