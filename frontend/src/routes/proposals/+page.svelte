<script lang="ts">
  import { onMount } from 'svelte';
  import Heading from '#lib/Heading.svelte';
  import { reserve, closing, money } from '#lib/ledger.ts';
  const available = closing.balance - reserve;
  const deposit = Math.floor(available / 4 / 10000) * 10000;
  const items = [
    { id:'reserve', category:'Cash reserve', title:'Keep January’s fixed bills covered', amount:reserve,
      analysis:'Rent, wage tax, energy, social security and payroll are due in January.',
      rationale:'The reserve equals the five payments on your cashflow calendar.',
      effect:'Record an earmarked cash reserve in this browser’s simulation.' },
    { id:'deposit', category:'Fixed-term deposit', title:'Set aside a portion of surplus cash', amount:deposit,
      analysis:'The year closed with ' + money(closing.balance) + '. After scheduled bills, ' + money(available) + ' remains before variable costs.',
      rationale:'This example allocates one quarter of that remainder, rounded down to the nearest €100. Check supplier needs before approving.',
      effect:'Record a simulated deposit allocation. Terms and rates would need a separate quote.' }
  ];
  type Decision = 'Approved' | 'Declined';
  let decisions = $state<Record<string, Decision>>({});
  let confirming = $state('');
  let notice = $state('');
  const key = 'amalfi.decisions.2025.v1';
  onMount(()=>{try {decisions = JSON.parse(localStorage.getItem(key) || '{}') || {};} catch {notice='Saved decisions could not be loaded.';}});
  function decide(id:string, value:Decision) {
    decisions = {...decisions,[id]:value}; confirming='';
    try {localStorage.setItem(key,JSON.stringify(decisions)); notice='Decision saved in this browser.';} catch {notice='Decision recorded for this session only.';}
  }
</script>
<svelte:head><title>Proposals</title></svelte:head>
<Heading title="Proposals" period="Simulated decisions"/>
<p class="note">Demo proposals based on the 2025 statement. Decisions are saved in this browser.</p>
<div class="proposal-grid">{#each items as item}
  <article class="panel proposal"><div class="panel-head"><p class="eyebrow">{item.category}</p><span class="status">{decisions[item.id] ?? 'Awaiting approval'}</span></div>
    <h2>{item.title}</h2><strong class="amount">{money(item.amount)}</strong>
    <dl><dt>What we see</dt><dd>{item.analysis}</dd><dt>Why this amount</dt><dd>{item.rationale}</dd><dt>On approval</dt><dd>{item.effect}</dd></dl>
    {#if !decisions[item.id]}
      {#if confirming===item.id}<div class="confirm"><p>Approve this simulated allocation of {money(item.amount)}?</p><button class="action" onclick={()=>decide(item.id,'Approved')}>Confirm approval</button> <button onclick={()=>confirming=''}>Cancel</button></div>
      {:else}<div class="actions"><button class="action" onclick={()=>confirming=item.id}>Approve</button><button onclick={()=>decide(item.id,'Declined')}>Decline</button></div>{/if}
    {:else}<p class="decision">{decisions[item.id]} · Simulation recorded</p>{/if}
  </article>
{/each}</div><p class="minor" role="status">{notice}</p>
