<script lang="ts">
  import { euro, type ScheduledPayment } from '../forecast';
  import { linear, shortDay } from './scale';

  let { due, asOf, days = 31 }: { due: { date: string; payment: ScheduledPayment }[]; asOf: string; days?: number } = $props();
  let width = $state(0);

  const dayIndex = (iso: string) => Math.round((Date.parse(iso) - Date.parse(asOf)) / 86_400_000);
  // Running total of scheduled money out, as a step line: it jumps on each due date.
  let steps = $derived(due.filter((item) => item.payment.amount < 0).reduce<{ day: number; total: number }[]>((points, item) => {
    const total = (points.at(-1)?.total ?? 0) - item.payment.amount;
    const day = dayIndex(item.date);
    return points.at(-1)?.day === day ? [...points.slice(0, -1), { day, total }] : [...points, { day, total }];
  }, []));
  let total = $derived(steps.at(-1)?.total ?? 0);
  const height = 84;
  const margin = { top: 8, right: 6, bottom: 18, left: 6 };
  let x = $derived(linear(0, days, margin.left, width - margin.right));
  let y = $derived(linear(0, total || 1, height - margin.bottom, margin.top));
  let path = $derived(['M' + x(0) + ',' + y(0), ...steps.flatMap((step, index) => [
    'L' + x(step.day) + ',' + y(steps[index - 1]?.total ?? 0), 'L' + x(step.day) + ',' + y(step.total)
  ]), 'L' + x(days) + ',' + y(total)].join(' '));
  let biggest = $derived(steps.reduce((top, step, index) => {
    const jump = step.total - (steps[index - 1]?.total ?? 0);
    return jump > top.jump ? { day: step.day, jump } : top;
  }, { day: 0, jump: 0 }));
  const dateAt = (day: number) => new Date(Date.parse(asOf) + day * 86_400_000).toISOString().slice(0, 10);
</script>

<figure class="chart-figure outflow">
  <p class="chart-desc"><b>{euro(total)}</b> of fixed payments are due in the next {days} days; the largest day is {shortDay(dateAt(biggest.day))} ({euro(biggest.jump)}).</p>
  <div class="chart-box" bind:clientWidth={width}>
    {#if width > 0 && steps.length}
      <svg {width} {height} role="img" aria-label={`Running total of scheduled payments over the next ${days} days, reaching ${euro(total)}.`}>
        <path class="chart-reveal" d={path + ` L${x(days)},${y(0)} Z`} style:fill="var(--chart-out)" fill-opacity=".14"/>
        <path class="chart-reveal" d={path} fill="none" style:stroke="var(--chart-out)" stroke-width="2"/>
        <text x={margin.left} y={height - 4}>{shortDay(dateAt(1))}</text>
        <text x={width - margin.right} y={height - 4} text-anchor="end">{shortDay(dateAt(days))}</text>
      </svg>
    {/if}
  </div>
</figure>
