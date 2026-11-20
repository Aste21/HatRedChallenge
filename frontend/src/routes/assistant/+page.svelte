<script lang="ts">
  import { tick } from 'svelte';
  import Heading from '#lib/Heading.svelte';
  import { closing, lowest, reserve, money, dateLabel } from '#lib/ledger.ts';
  const topics = ['Why did cash fall in summer?', 'Which bills are due in January?', 'How much cash is available?'];
  let messages = $state<{question:string; answer:string; source:string; href:string}[]>([]);
  let draft = $state('');
  let last: HTMLDivElement;
  async function ask(text:string) {
    const question = text.trim();
    if (!question) return;
    let answer = '', source = 'Cashflow', href = '/';
    if (/summer|june|july|fall|low point|closure/i.test(question)) {
      answer='The three-week June closure interrupted sales while fixed payments continued. The lowest daily closing balance was ' + money(lowest.balance) + ' on ' + dateLabel(lowest.date) + '.';
    } else if (/bill|january|payroll|reserve|rent/i.test(question)) {
      answer='January’s known bills total ' + money(reserve) + ' across rent, wage tax, energy, social security and payroll. Variable supplier costs are additional.';
    } else if (/cash|available|surplus|balance|invest/i.test(question)) {
      answer='At year end Amalfi had ' + money(closing.balance) + '. Allowing for scheduled January bills leaves ' + money(closing.balance-reserve) + ' before variable costs.';
      source='Proposals'; href='/proposals';
    } else if (/news|brief|headlines/i.test(question)) {
      answer='Open Business news for relevant articles, sources and summaries from the news service.'; source='Business news'; href='/news';
    } else {
      answer='This demo can explain the closing balance, the summer cash gap, January bills and the business briefing. Pick one of those topics to explore the statement.';
    }
    messages=[...messages,{question,answer,source,href}]; draft=''; await tick(); last?.scrollIntoView({block:'nearest'});
  }
</script>
<svelte:head><title>Chat</title></svelte:head>
<Heading title="Chat" period="2025 statement"/>
<div class="chat panel"><div class="panel-head"><h2>Questions about your account</h2>{#if messages.length}<button class="textbtn" onclick={()=>messages=[]}>Clear conversation</button>{/if}</div>
  <p class="note">This preview uses prepared answers from the statement. The live model is not connected.</p>
  <div class="conversation" aria-live="polite">{#each messages as message}<div class="turn"><p class="eyebrow">You</p><p>{message.question}</p><p class="eyebrow reply">Assistant</p><p>{message.answer}</p><a href={message.href}>View {message.source.toLowerCase()}</a></div>{/each}<div bind:this={last}></div></div>
  <div class="suggestions">{#each topics as topic}<button onclick={()=>ask(topic)}>{topic}</button>{/each}</div>
  <form onsubmit={(e)=>{e.preventDefault();ask(draft);}}><label for="question">Your question</label><div class="compose"><input id="question" bind:value={draft} placeholder="Ask about your cashflow…" maxlength="1200"/><button class="action" disabled={!draft.trim()}>Send</button></div></form>
</div>
