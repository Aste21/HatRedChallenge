<script lang="ts">
  import { page } from '$app/state';
  import ThemeToggle from '#lib/ThemeToggle.svelte';
  import LoginDialog from '#lib/LoginDialog.svelte';
  import { PRODUCT_NAME, TAGLINE } from '#lib/brand.ts';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
  let loginOpen = $state(false);

  const title = `${PRODUCT_NAME} · AI cash flow forecasting and CFO assistant for small businesses`;
  const description = `${PRODUCT_NAME} forecasts your business account 90 days ahead, warns you before cash gets tight, `
    + 'suggests deposits or a credit line in plain language and never acts without your approval.';

  const features = [
    { icon: 'forecast', title: '90-day cash forecast', text: 'Your balance for the next three months, with a likely range and a bad case, built from your own bank history and 4,000 simulated futures.' },
    { icon: 'alert', title: 'Early warnings', text: 'See weeks ahead when rent, payroll and taxes will meet a quiet month, and how likely an overdraft really is.' },
    { icon: 'proposal', title: 'Proposals with reasons', text: 'Spare cash for a fixed-term deposit, or a credit line before a gap. Every proposal shows the numbers behind it.' },
    { icon: 'check', title: 'You approve everything', text: 'Nothing happens without your click. Approvals are recorded and confirmed, and in this demo they are simulated.' },
    { icon: 'news', title: 'News that affects you', text: 'Energy prices, tax changes, road works in your street: check what an article means for your cash flow in one click.' },
    { icon: 'chat', title: 'Ask in plain words', text: `"Can I afford a new oven in March?" ${PRODUCT_NAME} answers with your real figures and says so when it does not know.` }
  ];
  const steps = [
    { title: 'Connect your business account', text: 'Your statement is read and regular payments like rent, payroll and taxes are found automatically.' },
    { title: 'See what is coming', text: 'The overview shows your expected balance, the lowest point in a bad case and what you can safely set aside.' },
    { title: 'Decide with confidence', text: 'Review proposals that explain their reasoning, then approve or decline. You stay in charge.' }
  ];
  const showcase = [
    { eyebrow: 'Forecast', title: 'Know your lowest point before you reach it', text: 'A summer holiday, a slow January, a tax prepayment: the forecast shows when your balance gets low and by how much, so you can act in time instead of reacting to an overdraft.', points: ['Expected balance and likely range', 'Chance of going below €0', 'Your cash buffer on every chart'] },
    { eyebrow: 'Proposals', title: 'Put spare cash to work, safely', text: 'When the forecast shows money you will not need, you get a proposal for a fixed-term deposit, sized so that your buffer stays untouched even in a bad case.', points: ['Amount, term and illustrative interest', 'A step-by-step "how we got this amount"', 'Alternatives that never use the same cash twice'] },
    { eyebrow: 'Your dashboard', title: 'Arrange it the way you think', text: 'Show the cards you care about, hide the rest, drag them into your order and make them wider or narrower. Light or dark, on a desktop or your phone.', points: ['Liquidity, forecast, spending and weekday patterns', 'A calendar of your whole year', 'Works with the keyboard and screen readers'] }
  ];
  const trust = [
    { title: 'You decide, always', text: `${PRODUCT_NAME} proposes. Only you approve. Every recommendation says what happens if you click.` },
    { title: 'Explainable numbers', text: 'Figures come from calculations on your data, never from the language model. The model only explains them.' },
    { title: 'Your data stays yours', text: 'Each business sees only its own account, decisions and conversations.' },
    { title: 'Open, in-house AI', text: 'Runs on Red Hat OpenShift AI with an open-source model served in the cluster, not on a public chatbot.' }
  ];
  const faq = [
    { question: `Who is ${PRODUCT_NAME} for?`, answer: 'Owners of small businesses without a finance department: restaurants, shops, workshops and practices that want to see their cash flow ahead without spreadsheets.' },
    { question: 'Does it move money on its own?', answer: 'No. It never executes anything without your approval. In this demo every approval is simulated, and no real bank is involved.' },
    { question: 'Where do the numbers come from?', answer: 'From your bank statement: the forecast is calculated from your past income, costs and regular payments. The language model only explains the results in plain words.' },
    { question: 'Are the interest rates real offers?', answer: 'No. Deposit offers and rates in the demo are illustrative. A real offer would always come from your bank.' },
    { question: 'Can I try it now?', answer: 'Yes. Log in with the demo account of Pizzeria Amalfi in Frankfurt: username "amalfi", password "amalfi".' }
  ];

  let canonical = $derived(new URL('/', page.url.origin).href);
  let structuredData = $derived(JSON.stringify([
    {
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      name: PRODUCT_NAME,
      applicationCategory: 'FinanceApplication',
      operatingSystem: 'Web',
      description,
      url: canonical
    },
    {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faq.map((item) => ({ '@type': 'Question', name: item.question, acceptedAnswer: { '@type': 'Answer', text: item.answer } }))
    }
  ]).replace(/</g, '\\u003c'));

  function startDemo() {
    if (data.signedIn) location.assign('/overview');
    else loginOpen = true;
  }
</script>

<svelte:head>
  <meta name="description" content={description} />
  <link rel="canonical" href={canonical} />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content={PRODUCT_NAME} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:url" content={canonical} />
  <meta property="og:image" content={new URL('/og-image.png', page.url.origin).href} />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={title} />
  <meta name="twitter:description" content={description} />
</svelte:head>

<a class="skip" href="#workspace">Skip to content</a>
<header class="landing-head">
  <div class="container nav-content">
    <a class="brand" href="/">{PRODUCT_NAME}</a>
    <nav class="landing-nav" aria-label="Page sections">
      <a href="#features">Features</a>
      <a href="#how-it-works">How it works</a>
      <a href="#trust">Security</a>
      <a href="#faq">FAQ</a>
    </nav>
    <div class="nav-tools">
      <ThemeToggle />
      {#if data.signedIn}
        <a class="button action" href="/overview">Open dashboard</a>
      {:else}
        <!-- The link works without JavaScript; with it, the login opens as a dialog on this page. -->
        <a class="button" href="/login" onclick={(event) => { event.preventDefault(); loginOpen = true; }}>Log in</a>
      {/if}
    </div>
  </div>
</header>

<main id="workspace" class="landing">
  <section class="hero container" aria-labelledby="hero-title">
    <div class="hero-text enter">
      <p class="eyebrow">{TAGLINE}</p>
      <h1 id="hero-title">See your cash flow weeks ahead. Decide before it gets tight.</h1>
      <p class="hero-lead">{PRODUCT_NAME} is a CFO assistant for small businesses. It watches your business account and relevant news, forecasts your balance for the next 90 days and suggests clear next steps. You approve every one of them.</p>
      <div class="hero-actions">
        <button class="action large" onclick={startDemo}>{data.signedIn ? 'Open your dashboard' : 'Try the live demo'}</button>
        <a class="button large" href="#how-it-works">See how it works</a>
      </div>
      <ul class="hero-facts" aria-label="Key facts">
        <li>No setup for the demo</li>
        <li>Nothing happens without your approval</li>
        <li>Runs on Red Hat OpenShift AI</li>
      </ul>
    </div>

    <div class="hero-visual enter" style:--i="2" role="img" aria-label="Preview of the dashboard: expected balance €58,405 in 90 days, 0 % chance of an overdraft, €7,391 safe to set aside, and a forecast line that stays above the cash buffer.">
      <div class="preview-bar" aria-hidden="true"><i></i><i></i><i></i><span>Overview</span></div>
      <div class="preview-kpis" aria-hidden="true">
        <div><span>Expected in 90 days</span><b>€58,405</b></div>
        <div><span>Chance below €0</span><b>0 %</b></div>
        <div><span>Safe to set aside</span><b>€7,391</b></div>
      </div>
      <svg viewBox="0 0 420 200" aria-hidden="true">
        <line class="hero-grid" x1="10" x2="410" y1="40" y2="40"/>
        <line class="hero-grid" x1="10" x2="410" y1="95" y2="95"/>
        <line class="hero-grid" x1="10" x2="410" y1="150" y2="150"/>
        <path class="hero-band" d="M10 120 C 70 100, 110 140, 170 100 S 300 60, 410 40 L 410 95 C 300 115, 240 150, 170 140 S 70 145, 10 130 Z"/>
        <line class="hero-buffer" x1="10" x2="410" y1="165" y2="165"/>
        <path class="hero-line" d="M10 125 C 70 120, 110 142, 170 118 S 300 85, 410 66"/>
        <circle class="hero-dot" cx="410" cy="66" r="6"/>
        <text x="408" y="183" text-anchor="end">Cash buffer</text>
      </svg>
      <div class="preview-proposal" aria-hidden="true">
        <span class="tag">Needs your approval</span>
        <b>Put €7,391 into a 90-day deposit</b>
        <span class="minor">Illustrative interest ≈ €76 · simulated</span>
      </div>
    </div>
  </section>

  <section class="container section" id="features" aria-labelledby="features-title">
    <p class="eyebrow">Features</p>
    <h2 id="features-title" class="section-title">Everything a finance department would tell you, in plain language</h2>
    <div class="feature-grid">
      {#each features as feature, index (feature.title)}
        <article class="panel feature enter" style:--i={index}>
          <span class="feature-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              {#if feature.icon === 'forecast'}<path d="M3 17l5-5 4 3 8-8"/><path d="M14 7h6v6"/>
              {:else if feature.icon === 'alert'}<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/>
              {:else if feature.icon === 'proposal'}<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>
              {:else if feature.icon === 'check'}<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>
              {:else if feature.icon === 'news'}<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h6M7 13h10M7 16h10"/>
              {:else}<path d="M4 5h16v11H9l-5 4z"/>{/if}
            </svg>
          </span>
          <h3>{feature.title}</h3>
          <p class="note">{feature.text}</p>
        </article>
      {/each}
    </div>
  </section>

  <section class="container section" id="how-it-works" aria-labelledby="steps-title">
    <p class="eyebrow">How it works</p>
    <h2 id="steps-title" class="section-title">From bank statement to a clear decision in three steps</h2>
    <ol class="steps">
      {#each steps as step, index (step.title)}
        <li class="panel"><span class="step-number" aria-hidden="true">{index + 1}</span><div><h3>{step.title}</h3><p class="note">{step.text}</p></div></li>
      {/each}
    </ol>
  </section>

  <section class="container section showcase" aria-label="Product tour">
    {#each showcase as item, index (item.title)}
      <article class="showcase-item" class:reverse={index % 2 === 1}>
        <div>
          <p class="eyebrow">{item.eyebrow}</p>
          <h2 class="section-title">{item.title}</h2>
          <p class="hero-lead">{item.text}</p>
          <ul class="checks">{#each item.points as point (point)}<li>{point}</li>{/each}</ul>
        </div>
        <div class="showcase-art panel" aria-hidden="true">
          {#if index === 0}
            <svg viewBox="0 0 360 200">
              <path class="hero-band" d="M10 70 C 60 60, 90 110, 140 150 S 230 90, 350 50 L 350 90 C 240 120, 200 170, 140 170 S 60 95, 10 85 Z"/>
              <line class="hero-buffer" x1="10" x2="350" y1="140" y2="140"/>
              <path class="hero-line" d="M10 78 C 60 75, 95 120, 140 158 S 230 100, 350 70"/>
              <circle class="showcase-risk" cx="140" cy="168" r="7"/>
              <text x="140" y="194" text-anchor="middle">Lowest point in a bad case</text>
            </svg>
          {:else if index === 1}
            <div class="art-waterfall">
              <span>Balance today</span><i style:--w="100%" style:--x="0%" class="in"></i>
              <span>Possible dip</span><i style:--w="14%" style:--x="86%" class="risk"></i>
              <span>Cash buffer</span><i style:--w="64%" style:--x="22%" class="buffer"></i>
              <span>Safe to set aside</span><i style:--w="22%" style:--x="0%" class="result"></i>
            </div>
          {:else}
            <div class="art-grid"><i class="wide"></i><i></i><i></i><i class="wide"></i><i class="full"></i></div>
          {/if}
        </div>
      </article>
    {/each}
  </section>

  <section class="container section" id="trust" aria-labelledby="trust-title">
    <p class="eyebrow">Security and control</p>
    <h2 id="trust-title" class="section-title">Built to support your decisions, not to make them</h2>
    <div class="trust-grid">
      {#each trust as item (item.title)}
        <div class="trust-item"><h3>{item.title}</h3><p class="note">{item.text}</p></div>
      {/each}
    </div>
  </section>

  <section class="container section faq" id="faq" aria-labelledby="faq-title">
    <p class="eyebrow">FAQ</p>
    <h2 id="faq-title" class="section-title">Questions owners ask</h2>
    {#each faq as item (item.question)}
      <details class="faq-item"><summary>{item.question}</summary><p class="note">{item.answer}</p></details>
    {/each}
  </section>

  <section class="container cta-band" aria-labelledby="cta-title">
    <h2 id="cta-title">See your next 90 days in a minute</h2>
    <p>Log in with the demo account of Pizzeria Amalfi and explore the forecast, the proposals and the chat with {PRODUCT_NAME}.</p>
    <button class="action large" onclick={startDemo}>{data.signedIn ? 'Open your dashboard' : 'Try the live demo'}</button>
  </section>
</main>

<footer class="landing-foot">
  <div class="container foot-grid">
    <div><a class="brand" href="/">{PRODUCT_NAME}</a><p class="minor">{TAGLINE}.</p></div>
    <nav aria-label="Footer"><a href="#features">Features</a><a href="#how-it-works">How it works</a><a href="#trust">Security</a><a href="#faq">FAQ</a></nav>
    <p class="minor">A demo built for the Commerzbank Collabothon 2026. Figures and offers are illustrative; nothing touches a real bank. © 2026</p>
  </div>
</footer>

<LoginDialog bind:open={loginOpen} />
<!-- Structured data for search engines; valid in the body, and keeps <svelte:head> free of raw HTML. -->
{@html `<script type="application/ld+json">${structuredData}</script>`}
