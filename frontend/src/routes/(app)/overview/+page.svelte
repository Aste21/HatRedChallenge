<script lang="ts">
  import { onMount } from 'svelte';
  import { flip } from 'svelte/animate';
  import { prefersReducedMotion } from 'svelte/motion';
  import AnimatedNumber from '#lib/AnimatedNumber.svelte';
  import BalanceChart from '#lib/BalanceChart.svelte';
  import MonthlyFlowChart from '#lib/charts/MonthlyFlowChart.svelte';
  import SpendingChart from '#lib/charts/SpendingChart.svelte';
  import WeekdayChart from '#lib/charts/WeekdayChart.svelte';
  import CalendarHeatmap from '#lib/charts/CalendarHeatmap.svelte';
  import OutflowChart from '#lib/charts/OutflowChart.svelte';
  import { dateLabel, money, useLedger } from '#lib/ledger.ts';
  import { providePageDetails } from '#lib/chat/page-context.ts';
  import CustomChart from '#lib/charts/CustomChart.svelte';
  import { layout, spanLabels, spanNames, widgets, type Span } from '#lib/dashboard.svelte.ts';
  import { customCharts } from '#lib/custom-charts.svelte.ts';
  import { CHART_TYPES, chartTypeLabels, isBreakdown, type ChartType } from '#lib/charts/custom.ts';
  import { describeEvent, euro, eventStart, percent, upcomingPayments, worstDay, type ChartMarker, type Forecast } from '#lib/forecast.ts';
  import type { PageProps } from './$types';
  const { months, december, closing, bills, lowest, scenario, spending, weekdayTakings } = useLedger();

  let { data }: PageProps = $props();
  let allMonths = $state(false);
  let forecast = $state<Forecast | null>(null);
  let forecastLoaded = $state(false);
  let withAssumptions = $state(false);
  let customizing = $state(false);
  let dragging = $state<string | null>(null);
  let resizing = $state<string | null>(null);
  let announcement = $state('');
  const newest = [...months].reverse();
  const titles = Object.fromEntries(widgets.map((widget) => [widget.id, widget.title]));

  /** The two views of the page: the ready-made widgets, or the charts the owner made with the assistant. */
  type View = 'ready' | 'own';
  const views: { id: View; label: string }[] = [{ id: 'ready', label: 'Ready-made' }, { id: 'own', label: 'Your charts' }];
  const panelIds: Record<View, string> = { ready: 'view-ready', own: 'your-charts' };
  const ownChartsHash = `#${panelIds.own}`;
  const readyChartsHash = `#${panelIds.ready}`;
  let selectedView = $state<View | null>(null);
  let view = $derived<View>(selectedView ?? (customCharts.charts.length ? 'own' : 'ready'));
  const tabs: Record<View, HTMLButtonElement | undefined> = $state({ ready: undefined, own: undefined });

  const viewFromHash = (): View | null => {
    if (location.hash === ownChartsHash) return 'own';
    if (location.hash === readyChartsHash) return 'ready';
    return null;
  };
  /** Switch the view and keep the address shareable. */
  function showView(next: View, focus = false) {
    selectedView = next;
    confirmingDelete = null;
    const url = new URL(location.href);
    url.hash = next === 'own' ? ownChartsHash : readyChartsHash;
    if (url.href !== location.href) history.replaceState(history.state, '', url.pathname + url.search + url.hash);
    if (focus) tabs[next]?.focus();
  }
  /** Tabs follow the keyboard pattern of a tab list: arrows, Home and End move between them. */
  function tabKeydown(event: KeyboardEvent) {
    const index = views.findIndex((candidate) => candidate.id === view);
    const target = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: views.length - 1 }[event.key];
    if (target === undefined) return;
    event.preventDefault();
    showView(views[(target + views.length) % views.length].id, true);
  }

  // svelte-ignore state_referenced_locally
  onMount(() => {
    layout.restore(data.account.id);
    selectedView = viewFromHash();
    const followHash = () => { selectedView = viewFromHash(); };
    window.addEventListener('hashchange', followHash);
    return () => window.removeEventListener('hashchange', followHash);
  });

  // The forecast streams in after the page is shown; until then the chart uses the illustrative scenario.
  $effect(() => {
    let current = true;
    data.forecast.then((loaded) => { if (current) { forecast = loaded; forecastLoaded = true; } });
    return () => { current = false; };
  });

  let hasAssumptions = $derived(!!forecast && forecast.with_assumptions.events.length > forecast.official.events.length);
  let showingEstimates = $derived(withAssumptions && hasAssumptions);
  let active = $derived(forecast ? (showingEstimates ? forecast.with_assumptions : forecast.official) : null);
  let other = $derived(forecast && hasAssumptions ? (showingEstimates ? forecast.official : forecast.with_assumptions) : null);
  let worst = $derived(active ? worstDay(active) : null);
  let lastDay = $derived(active ? active.daily[active.daily.length - 1] : null);
  let upcoming = $derived(forecast ? upcomingPayments(forecast.schedule, forecast.as_of) : []);
  let events = $derived(forecast?.with_assumptions.events ?? []);
  let markers = $derived<ChartMarker[]>(events.flatMap((event, index) => {
    const start = eventStart(event);
    return start ? [{ date: start, number: index + 1, label: describeEvent(event) }] : [];
  }));

  /** The built-in widgets and the owner's own charts are arranged the same way, each in its own grid. */
  type Arrangement = typeof layout | typeof customCharts;
  const titleOf = (id: string) => titles[id] ?? customCharts.get(id)?.spec.title ?? 'Chart';
  // Cards only move within their own section: a chart is never dropped among the built-in widgets.
  const arrangementOf = (id: string): Arrangement => (titles[id] ? layout : customCharts);

  function move(id: string, direction: -1 | 1) {
    const arrangement = arrangementOf(id);
    arrangement.move(id, direction);
    announcement = `${titleOf(id)} moved to position ${arrangement.visible.indexOf(id) + 1} of ${arrangement.visible.length}.`;
  }
  function setSpan(id: string, span: Span) {
    const arrangement = arrangementOf(id);
    arrangement.resize(id, span);
    announcement = `${titleOf(id)} is now ${spanNames[arrangement.spans[id]]}.`;
  }
  /** Drag the right edge of a card: its width snaps to a third, a half, two thirds or full width. */
  function startResize(event: PointerEvent, id: string) {
    const handle = event.currentTarget as HTMLElement;
    const grid = handle.closest('.dashboard') as HTMLElement | null;
    if (!grid) return;
    event.preventDefault();
    const arrangement = arrangementOf(id);
    const card = handle.closest('.widget') as HTMLElement;
    const gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
    const column = (grid.getBoundingClientRect().width + gap) / 12;
    const left = card.getBoundingClientRect().left;
    resizing = id;
    handle.setPointerCapture(event.pointerId);
    const follow = (moveEvent: PointerEvent) => arrangement.resize(id, Math.max(1, Math.round((moveEvent.clientX - left + gap) / column)));
    const stop = () => {
      handle.removeEventListener('pointermove', follow);
      handle.removeEventListener('pointerup', stop);
      handle.removeEventListener('pointercancel', stop);
      resizing = null;
      announcement = `${titleOf(id)} is now ${spanNames[arrangement.spans[id]]}.`;
    };
    handle.addEventListener('pointermove', follow);
    handle.addEventListener('pointerup', stop);
    handle.addEventListener('pointercancel', stop);
  }
  function hide(id: string) {
    layout.toggle(id);
    announcement = `${titles[id]} hidden. You can show it again in the list above.`;
  }
  function dragOver(event: DragEvent, id: string) {
    if (!dragging || dragging === id) return;
    const arrangement = arrangementOf(id);
    if (arrangementOf(dragging) !== arrangement) return;
    event.preventDefault();
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const after = event.clientY > box.top + box.height / 2;
    const visible = arrangement.visible;
    arrangement.placeBefore(dragging, after ? visible[visible.indexOf(id) + 1] ?? null : id);
  }
  function startDrag(event: DragEvent, id: string) {
    dragging = id;
    event.dataTransfer?.setData('text/plain', id);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }
  function endDrag() {
    if (dragging) announcement = `${titleOf(dragging)} moved to position ${arrangementOf(dragging).visible.indexOf(dragging) + 1}.`;
    dragging = null;
  }

  // Deleting asks once more on the same button, so a slip of the finger never removes a chart.
  let confirmingDelete = $state<string | null>(null);
  function deleteChart(id: string) {
    if (confirmingDelete !== id) { confirmingDelete = id; return; }
    const title = titleOf(id);
    customCharts.remove(id);
    confirmingDelete = null;
    announcement = `${title} deleted.`;
  }

  function forecastDetails(): string[] {
    if (!forecast || !active || !worst || !lastDay) {
      return [
        'Chart "Forecast" tab, illustrative January 2026 scenario with scheduled bills only and no receipts:',
        ...[7, 14, 31].map((days) => `after ${days} days (${dateLabel(scenario[days - 1].date)}): ${money(scenario[days - 1].balance)}`)
      ];
    }
    const daily = active.daily;
    return [
      `Forecast shown: ${active === forecast.official ? 'official changes only' : 'including assumptions from news'}.`,
      'Chart "Forecast" tab, forecast from the forecasting service (expected balance, likely range 5th–95th percentile):',
      ...[30, 60, 90].filter((days) => days <= daily.length).map((days) => {
        const day = daily[days - 1];
        return `after ${days} days (${dateLabel(day.date)}): ${euro(day.p50)} (likely ${euro(day.p5)} to ${euro(day.p95)})`;
      }),
      `Lowest balance in a bad case: ${euro(worst.p5)} on ${dateLabel(worst.date)}. Chance of going below €0: ${percent(active.p_below_zero)}.`,
      `Cash buffer: ${euro(active.buffer.amount)}. Safe to set aside: ${active.safe_to_lock.map((limit) => `${limit.days} days ${euro(limit.amount)}`).join('; ')}.`,
      ...events.map((event, index) => `News ${index + 1} taken into account (${event.certainty}): ${describeEvent(event)}${event.why ? ` — ${event.why}` : ''}`)
    ];
  }

  // The charts hide figures that are not plain text on screen; give them to the assistant.
  providePageDetails(() => [
    `Overview widgets shown: ${layout.visible.map((id) => titles[id]).join(', ')}.`,
    customCharts.charts.length
      ? `The owner's own charts (made with the assistant): ${customCharts.charts.map((chart) => chart.spec.title).join(', ')}.`
      : 'The owner has not added charts of their own yet.',
    'Monthly balances 2025 (money in / money out / closing balance):',
    ...months.map((row) => `${row.name}: ${money(row.income)} / ${money(row.costs)} / ${money(row.balance)}`),
    `Lowest daily balance: ${money(lowest.balance)} on ${dateLabel(lowest.date)}.`,
    'Money out in 2025 by category: ' + spending.map((row) => `${row.name} ${money(row.cents)}`).join('; ') + '.',
    'Average daily debit-card takings Monday to Sunday: ' + weekdayTakings.map(money).join(', ') + '.',
    ...forecastDetails()
  ].join('\n'));
</script>

<h1 class="sr-only">Overview</h1>

<div class="dashboard-toolbar">
  <div class="view-tabs" role="tablist" aria-label="What to show">
    {#each views as option (option.id)}
      <button bind:this={tabs[option.id]} role="tab" id="tab-{option.id}" aria-selected={view === option.id}
        aria-controls={view === option.id ? panelIds[option.id] : undefined} tabindex={view === option.id ? 0 : -1}
        onclick={() => showView(option.id)} onkeydown={tabKeydown}>
        {option.label}
        {#if option.id === 'own'}
          <span class="tab-count" aria-hidden="true">{customCharts.charts.length}</span>
          <span class="sr-only">({customCharts.charts.length} {customCharts.charts.length === 1 ? 'chart' : 'charts'})</span>
        {/if}
      </button>
    {/each}
  </div>
  {#if view === 'ready' || customCharts.charts.length}
    <button class="customize-toggle" aria-pressed={customizing} onclick={() => customizing = !customizing}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></svg>
      {customizing ? 'Done' : 'Customize overview'}
    </button>
  {/if}
</div>

{#if customizing && view === 'ready'}
  <section class="panel customize enter" aria-labelledby="customize-title">
    <div class="panel-head"><h2 id="customize-title">Customize your overview</h2><button class="textbtn" onclick={() => layout.reset()}>Reset to default</button></div>
    <p class="note">Choose what you want to see. Drag a card by its title bar to move it, or use its arrow buttons. Make a card wider or narrower with its size buttons or by dragging its right edge, so the cards fill each row. Your layout is saved in this browser.</p>
    <ul class="widget-choices">
      {#each layout.order as id (id)}
        <li><label><input type="checkbox" checked={!layout.hidden.includes(id)} onchange={() => layout.toggle(id)} /> {titles[id]}</label></li>
      {/each}
    </ul>
  </section>
{:else if customizing && customCharts.charts.length}
  <p class="customize-hint enter">Drag a chart by its title bar to move it, or use its arrow buttons. Change its width with the size buttons or by dragging its right edge. You can also rename a chart, change its style or delete it.</p>
{/if}
<p class="sr-only" role="status">{announcement}</p>

{#if view === 'ready'}
<div class="view-panel" role="tabpanel" id="view-ready" aria-labelledby="tab-ready">
<div class="dashboard" class:customizing class:resizing={resizing !== null}>
  {#each layout.visible as id, position (id)}
    <div class="widget enter" class:dragging={dragging === id} style:--i={position} style:--span={layout.spans[id]}
      animate:flip={{ duration: prefersReducedMotion.current ? 0 : 240 }}
      role={customizing ? 'group' : undefined} aria-label={customizing ? titles[id] : undefined}
      ondragover={(event) => dragOver(event, id)} ondrop={(event) => event.preventDefault()}>
      {#if customizing}
        <!-- Cards move by their title bar, so the resize handle and the charts keep their own pointer gestures. -->
        <div class="widget-tools" draggable="true" role="toolbar" tabindex="-1" aria-label="Arrange {titles[id]}"
          ondragstart={(event) => startDrag(event, id)} ondragend={endDrag}>
          <span class="drag-handle" aria-hidden="true">⠿</span><b>{titles[id]}</b>
          <button disabled={position === 0} onclick={() => move(id, -1)} aria-label="Move {titles[id]} up">↑</button>
          <button disabled={position === layout.visible.length - 1} onclick={() => move(id, 1)} aria-label="Move {titles[id]} down">↓</button>
          <span class="size-buttons" role="group" aria-label="Width of {titles[id]}">
            {#each layout.spansFor(id) as span (span)}
              <button aria-pressed={layout.spans[id] === span} onclick={() => setSpan(id, span)} aria-label="{spanNames[span]}">{spanLabels[span]}</button>
            {/each}
          </span>
          <button onclick={() => hide(id)}>Hide</button>
        </div>
        <!-- Pointer-only shortcut for the size buttons above, which also work with the keyboard. -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span class="resize-handle" aria-hidden="true" draggable="false" title="Drag to resize" onpointerdown={(event) => startResize(event, id)}></span>
      {/if}

      {#if id === 'summary'}
        <div class="metrics">
          <section><h2>Closing balance</h2><strong><AnimatedNumber value={closing.balance} format={money} /></strong></section>
          <section><h2>December receipts</h2><strong><AnimatedNumber value={december.income} format={money} /></strong></section>
          <section><h2>December payments</h2><strong><AnimatedNumber value={december.costs} format={money} /></strong></section>
        </div>

      {:else if id === 'outlook'}
        {#if forecast && active && worst && lastDay}
          <section class="panel outlook enter" aria-labelledby="outlook-title">
            <div class="panel-head">
              <h2 id="outlook-title">Next {active.daily.length} days</h2>
              {#if hasAssumptions}
                <div class="switches" aria-label="Forecast scenario">
                  <button aria-pressed={!withAssumptions} onclick={() => withAssumptions = false}>Confirmed changes</button>
                  <button aria-pressed={withAssumptions} onclick={() => withAssumptions = true}>Including estimates</button>
                </div>
              {/if}
            </div>
            <div class="outlook-grid">
              <div>
                <h3>Expected balance on {dateLabel(lastDay.date)}</h3>
                <strong><AnimatedNumber value={active.end_balance_p50} format={euro} /></strong>
                <p class="minor">Likely between {euro(lastDay.p5)} and {euro(lastDay.p95)}</p>
              </div>
              <div class:warning={worst.p5 < 0}>
                <h3>Lowest balance in a bad case</h3>
                <strong><AnimatedNumber value={worst.p5} format={euro} /></strong>
                <p class="minor">Around {dateLabel(worst.date)}</p>
              </div>
              <div class:warning={active.p_below_zero > 0}>
                <h3>Chance of going below €0</h3>
                <strong><AnimatedNumber value={active.p_below_zero} format={percent} /></strong>
                <p class="minor">{active.p_below_zero > 0 ? 'An overdraft is possible in a bad case' : 'No overdraft expected'}</p>
              </div>
              <div>
                <h3>Safe to set aside</h3>
                <ul class="lock-list">
                  {#each active.safe_to_lock as limit (limit.days)}
                    <li><span>{limit.days} days</span><b><AnimatedNumber value={limit.amount} format={euro} /></b></li>
                  {/each}
                </ul>
              </div>
            </div>
            <p class="note">
              We always keep a cash buffer of {euro(active.buffer.amount)}{active.buffer.source === 'suggested' ? ' (one month of scheduled payments)' : ''}.
              "Safe to set aside" is what stays above that buffer even in a bad case. <a href="/proposals">See what you could do with it</a>
            </p>
          </section>
        {:else if !forecastLoaded}
          <section class="panel outlook" aria-busy="true" aria-label="Loading your forecast">
            <span class="skeleton skeleton-line" style:width="9rem"></span>
            <div class="outlook-grid">
              {#each [0, 1, 2, 3] as placeholder (placeholder)}
                <div><span class="skeleton skeleton-line" style:width="70%"></span><span class="skeleton skeleton-line wide"></span><span class="skeleton skeleton-line" style:width="50%"></span></div>
              {/each}
            </div>
          </section>
        {:else}
          <section class="panel outlook"><h2>Next 90 days</h2><p class="note">The forecast is not available right now. Try refreshing in a moment.</p></section>
        {/if}

      {:else if id === 'liquidity'}
        <BalanceChart mode="history" />

      {:else if id === 'forecast'}
        <BalanceChart mode="forecast" forecast={active?.daily ?? null} compare={other?.daily ?? null}
          activeLabel={showingEstimates ? 'Including estimates' : 'Confirmed changes'}
          compareLabel={showingEstimates ? 'Confirmed changes' : 'Including estimates'}
          buffer={active?.buffer.amount ?? null} {markers} />

      {:else if id === 'payments'}
        <section class="panel schedule">
          {#if forecast}
            <div class="panel-head"><h2>Upcoming payments</h2><span class="minor">Next 31 days</span></div>
            <OutflowChart due={upcoming} asOf={forecast.as_of} />
            <ul>
              {#each upcoming as item (item.date + item.payment.name)}
                <li>
                  <time datetime={item.date}>{new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(item.date))}</time>
                  <span>{item.payment.name}{#if item.payment.last_reference}<small class="minor" title={item.payment.last_reference}>Last: {item.payment.last_reference}</small>{/if}</span><b>{euro(item.payment.amount)}</b>
                </li>
              {:else}
                <li>No scheduled payments in the next 31 days.</li>
              {/each}
            </ul>
            <p class="minor">Found automatically in your bank history and included in the forecast.</p>
          {:else}
            <div class="panel-head"><h2>Scheduled payments</h2><span class="minor">January 2026</span></div>
            <ul>
              {#each bills as bill}
                <li><time datetime={'2026-01-' + String(bill.day).padStart(2,'0')}>Jan {bill.day}</time><span>{bill.name}</span><b>{money(bill.cents)}</b></li>
              {/each}
            </ul>
          {/if}
          <a href="/proposals">Review proposals</a>
        </section>

      {:else if id === 'news'}
        <section class="panel events" aria-labelledby="events-title">
          <div class="panel-head"><h2 id="events-title">News in your forecast</h2><a href="/news">Business news</a></div>
          {#if events.length}
            <ol>
              {#each events as event, index (index)}
                <li>
                  <span class="marker-number" aria-hidden="true">{index + 1}</span>
                  <span class="tag" class:estimate={event.certainty !== 'official'}>{event.certainty === 'official' ? 'Confirmed' : 'Estimate'}</span>
                  <div><b>{describeEvent(event)}</b>{#if event.why}<p class="minor">{event.why}</p>{/if}</div>
                </li>
              {/each}
            </ol>
            <p class="note">Confirmed changes are always in the forecast. Estimates only count when you choose "Including estimates". The numbers match the markers on the balance chart.</p>
          {:else if forecast}
            <p class="note">No news is part of the forecast yet. On Business news, choose "Check impact on my forecast" for an article.</p>
          {:else}
            <p class="note">News can be added once the forecast is available.</p>
          {/if}
        </section>

      {:else if id === 'monthly'}
        <section class="panel">
          <MonthlyFlowChart />
          <div class="panel-head monthly-head">
            <h3>Monthly balances</h3>
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

      {:else if id === 'spending'}
        <section class="panel"><SpendingChart /></section>
      {:else if id === 'weekday'}
        <section class="panel"><WeekdayChart /></section>
      {:else if id === 'calendar'}
        <section class="panel"><CalendarHeatmap /></section>
      {/if}
    </div>
  {:else}
    <p class="note">All widgets are hidden. Choose "Customize overview" to show some again.</p>
  {/each}
</div>
</div>

{:else}
<!-- The id matches the "#your-charts" link the Chat shows after a chart is added. -->
<div class="view-panel custom-charts" role="tabpanel" id="your-charts" aria-labelledby="tab-own">
  <p class="minor view-intro">Charts you made with the assistant. All figures come from your bank statement.</p>
  {#if customCharts.charts.length}
    <div class="dashboard" class:customizing class:resizing={resizing !== null}>
      {#each customCharts.charts as chart, position (chart.id)}
        {@const id = chart.id}
        <div class="widget enter" class:dragging={dragging === id} style:--i={position} style:--span={chart.span}
          animate:flip={{ duration: prefersReducedMotion.current ? 0 : 240 }}
          role={customizing ? 'group' : undefined} aria-label={customizing ? chart.spec.title : undefined}
          ondragover={(event) => dragOver(event, id)} ondrop={(event) => event.preventDefault()}>
          {#if customizing}
            <div class="widget-tools" draggable="true" role="toolbar" tabindex="-1" aria-label="Arrange {chart.spec.title}"
              ondragstart={(event) => startDrag(event, id)} ondragend={endDrag}>
              <span class="drag-handle" aria-hidden="true">⠿</span>
              <label class="sr-only" for="chart-title-{id}">Title of the chart</label>
              <!-- Text inside the input stays selectable: dragging starts only from the rest of the bar. -->
              <input class="chart-title-input" id="chart-title-{id}" value={chart.spec.title} maxlength="80" draggable="false"
                ondragstart={(event) => event.preventDefault()}
                onchange={(event) => { customCharts.rename(id, event.currentTarget.value); event.currentTarget.value = customCharts.get(id)?.spec.title ?? ''; }} />
              <button disabled={position === 0} onclick={() => move(id, -1)} aria-label="Move {chart.spec.title} up">↑</button>
              <button disabled={position === customCharts.charts.length - 1} onclick={() => move(id, 1)} aria-label="Move {chart.spec.title} down">↓</button>
              <span class="size-buttons" role="group" aria-label="Width of {chart.spec.title}">
                {#each customCharts.spansFor(id) as span (span)}
                  <button aria-pressed={chart.span === span} onclick={() => setSpan(id, span)} aria-label="{spanNames[span]}">{spanLabels[span]}</button>
                {/each}
              </span>
              {#if !isBreakdown(chart.spec)}
                <label class="sr-only" for="chart-type-{id}">Chart style</label>
                <select id="chart-type-{id}" value={chart.spec.chart_type}
                  onchange={(event) => customCharts.setChartType(id, event.currentTarget.value as ChartType)}>
                  {#each CHART_TYPES as chartType (chartType)}<option value={chartType}>{chartTypeLabels[chartType]}</option>{/each}
                </select>
              {/if}
              <button class="danger" class:confirming={confirmingDelete === id} onclick={() => deleteChart(id)}
                onblur={() => { if (confirmingDelete === id) confirmingDelete = null; }}>
                {confirmingDelete === id ? 'Click again to delete' : 'Delete'}
              </button>
            </div>
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <span class="resize-handle" aria-hidden="true" draggable="false" title="Drag to resize" onpointerdown={(event) => startResize(event, id)}></span>
          {/if}
          <section class="panel"><CustomChart spec={chart.spec} /></section>
        </div>
      {/each}
    </div>
  {:else}
    <div class="panel custom-empty">
      <p>You have no charts of your own yet.</p>
      <p class="minor">Ask the assistant for one in the Chat, for example "Show money in and out per week as a line chart", then choose "Add to overview".</p>
      <a class="button action" href="/assistant">Open the Chat</a>
    </div>
  {/if}
</div>
{/if}
