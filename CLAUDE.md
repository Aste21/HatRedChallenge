# CLAUDE.md — Autonomous CFO (Commerzbank Collabothon 2026, Red Hat challenge)

Guidance for AI coding agents (Claude Code, OpenClaw, Pi, Aider) and humans working in this repo.
Read this file fully before writing code. When something here conflicts with a direct instruction from a team member, ask.

---

## 1. What we are building

An **AI-powered CFO assistant for SME owners** (no dedicated CFO). It monitors the company bank account and
business news, forecasts liquidity, proposes explainable next steps, and **never executes anything without the
owner's approval** (execution is simulated).

Demo company: **Pizzeria Amalfi** (Frankfurt, owner Vincenzo Amalfi), full year 2025 bank statement (see §5).

Every agent output must make these four things explicit (challenge requirement):

| Field | Meaning |
|---|---|
| `analysis` | What the agent observed and computed on its own |
| `recommendation` | What it proposes, in plain language a non-expert understands |
| `requires_approval` | Whether the owner must approve before anything happens (default `true`) |
| `execution_mode` | `"simulated"` for everything in this project — nothing touches a real bank |

Plus a short `rationale` (the business logic behind the recommendation, with the numbers it used).
Theme "Innovations for all generations": UI must be understandable for owners with low technical confidence.

### Scoring we optimise for
- **Hard requirements (no points without them):** the app runs on our OpenShift cluster AND uses an LLM served on
  OpenShift AI. A working end-to-end app is mandatory.
- **Soft:** use-case quality, explainability, UI/UX.
- **Targeted bonuses:** vLLM on RHOAI, llm-d, MLflow tracing/evaluation, Jupyter on RHOAI, Dev Spaces + OSS code
  assistant, personal agentic assistant (OpenClaw/Pi) on OpenShift. Bonuses are weighted low — never trade app
  quality for a bonus.

---

## 2. Architecture

```
 INPUTS                       PROCESSING                                   OUTPUTS (UI pages)
 ──────                       ──────────                                   ──────────────────
 Bank account (CSV) ──► Cashflow ──► Liquidity prediction model ──► Predicted balance ──► [1] Cashflow: history + forecast (x days)
                                         ▲                               │
                                         │ features: sentiment, count    ▼
                                  Feature extraction            Investment agent (deposits, money
                                  from unstructured data        market funds, capex financing)
                                         ▲                               │
 WebSearch / RSS ──┐                     │                               ▼
 Verified sources ─┴─► News agent ──► Business-relevant info ──┬──► Investment instructions ──► [2] Proposed investments + "Approve" button
                      (tax + non-tax)   (e.g. tax changes)     │
                                                               ├──► LLM summary/headings ──► [3] News affecting the business + summary
                                                               │
                                                               └──► Notification system ──► e-mail / Slack (send_email(recipient, subject, body))
                                                                                            [4] Simple chatbot over all of the above
```

Components and their module location:

| Component | Path | Notes |
|---|---|---|
| Bank data loader + categoriser | `backend/app/data/` | Parses the CSV (§5), computes running balance, tags categories |
| Liquidity prediction | `ml/` (notebooks/training) + `backend/app/forecasting/` (serving) | Method TBD by owner (§9) |
| Feature extraction from news | `backend/app/agents/news/features.py` | Sentiment, counts — feeds liquidity model |
| News agent | `backend/app/agents/news/` | Source strategy TBD (§9) |
| Investment agent | `backend/app/agents/investment/` | Proposes instruments from forecast surplus |
| Notification system | `backend/app/notifications/` | `send_email(recipient, subject, body)`; delivery mode TBD (§9) |
| Chatbot | `backend/app/agents/chat/` | Answers questions using the other components as tools |
| Orchestration | `backend/app/graph/` | LangGraph; approval = graph interrupt (human-in-the-loop) |
| Frontend | `frontend/` | SvelteKit, 4 pages above |
| Deployment | `deploy/` | OpenShift manifests |

---

## 3. Tech stack

- **Backend:** Python ≥3.11, FastAPI, LangGraph, OpenAI-compatible client pointed at the in-cluster vLLM.
- **Frontend:** SvelteKit with **Svelte 5** (runes: `$state`, `$derived`, `$props`), TypeScript, UI text in English.
- **ML / experiments:** Jupyter workbench on OpenShift AI, MLflow for experiment tracking and agent tracing.
- **Package managers:** `uv` for Python, `npm` for the frontend (TBD — change here if the team decides otherwise).
- **Persistence:** SQLite file on a PVC for approvals, simulated transactions, notification outbox, chat history
  (TBD — keep the data layer behind a small repository module so it can be swapped).
- **Language:** all code, comments, identifiers, commit messages and UI text in **English**.

---

## 4. Repository layout (monorepo)

```
backend/            FastAPI app, agents, LangGraph graph, tests
  app/
    data/           CSV parsing, categorisation, balance computation
    forecasting/    liquidity forecast serving
    agents/         news/, investment/, chat/
    graph/          LangGraph wiring, approval interrupts
    notifications/  send_email + outbox
    api/            FastAPI routers
  tests/
frontend/           SvelteKit app
ml/                 Jupyter notebooks, training scripts (run on RHOAI workbench)
data/               raw sample data (read-only) and generated fixtures
deploy/             OpenShift manifests (Deployment, Service, Route, ConfigMap, PVC)
docs/               architecture notes, demo script, ai-logs/
```

---

## 5. Data: Pizzeria Amalfi bank statement 2025

File: `data/raw/pizzeria-amalfi-bank-statement-2025.csv` (read-only, never modify; write derived files elsewhere).
German online-banking export, similar to MT940.

### Format — parse exactly like this
- Separator `;`, every field quoted with `"`, UTF-8, header row present.
- Columns: `Account Number; Booking Date; Value Date; Transaction Type; Payment Reference; Beneficiary/Payer;
  Counterparty Account; Bank Code; Amount; Currency; Info`.
- Dates are `DD.MM.YY` (e.g. `31.12.25`) → parse to `datetime.date` (2025). Booking date == value date in this file.
- Amounts use a **decimal comma** (`-279,16`), no thousands separator. Negative = outflow.
- Rows are sorted **newest first** — sort ascending before any time-series work.
- **There is no balance column.** Opening balance on 2025-01-01 is **€2,500.00**; closing balance on 2025-12-31
  is **€33,266.34**. Running balance = opening balance + cumulative sum of EUR amounts (after FX conversion below).
- 1,125 rows: 1,113 in EUR, **12 in CHF**.
- **CHF rows** (`INTERNATIONAL WIRE TRANSFER`, 15th of each month, `-4166,67 CHF`): the EUR/CHF rate is only in the
  payment reference, e.g. `(4166.67 CHF @ 1.047 EUR/CHF)`. Convert with that rate (≈ €4,325–4,375). Never treat
  the CHF amount as EUR.
- Counterparty Account / Bank Code are empty for `GIRO CARD PAYMENT` rows.
- `DIRECT DEBIT` covers several different things (social security, energy, income/trade tax) — categorise by
  counterparty + reference, not by transaction type alone.

### Transaction types and categories

| Transaction Type | Rows | Counterparty | Category |
|---|---|---|---|
| CARD SETTLEMENT (DEBIT) | 335 | Pizzeria Amalfi Customers (Debit) | revenue_debit_card (daily) |
| CREDIT CARD PAYOUT | 143 | Commerzbank Global Pay | revenue_credit_card (≈ twice a week) |
| GIRO CARD PAYMENT | 292 | Central Wholesale Market | cogs_fresh_produce (near daily) |
| SUPPLIER PAYMENT | 239 | Asimex Wholesale Ltd / Fattoria La Vino GmbH | cogs_food / cogs_beverages |
| SALARY PAYMENT | 48 | 4 people | payroll (owner withdrawal included) |
| DIRECT DEBIT | 32 | TK / City Energy / Tax Office | social_security / utilities / tax_prepayment |
| TAX OFFICE TRANSFER | 12 | Tax Office Frankfurt am Main | payroll_tax |
| RENT PAYMENT | 12 | Main Street Real Estate GmbH | rent |
| INTERNATIONAL WIRE TRANSFER | 12 | Luigi Amalfi (Zurich) | capital_outflow_chf (FX exposure) |

### Known recurring schedule (use for forecasting and for explaining forecasts)

| Day | Item | Amount |
|---|---|---|
| 1st | Rent | €3,800.00 |
| 10th | Wage tax & solidarity surcharge | €880.00 |
| 10th | Energy & gas advance | €650.00 |
| 10 Mar/Jun/Sep/Dec | Income tax prepayment | €1,150.00 |
| 15th | Silent-partnership tranche to Zurich | 4,166.67 CHF (12 of 12 paid in 2025, 50,000 CHF total) |
| 15 Feb/May/Aug/Nov | Trade tax prepayment | €225.00 |
| 27th | Social security (Techniker Krankenkasse) | €2,650.00 |
| 28th | Net payroll (Vincenzo 3,200 / Yusuf 2,350 / Rosa 2,100 / Vanessa 950) | €8,600.00 |

### Story in the data (the demo narrative)
- **June shutdown:** 3-week vacation, zero revenue, fixed costs continue → overdraft. Lowest balance ≈ **−€22,097.60
  on 2025-07-03**. This is the event the liquidity agent must catch early and explain (e.g. propose a credit
  facility in May).
- **Q3–Q4 recovery** to €33,266.34 at year end → surplus the investment agent can place (fixed-term deposit,
  money market fund, capex financing).
- **Recurring CHF outflow** → FX exposure worth mentioning in recommendations.
- Data is AI-generated sample data provided by Commerzbank; not fully realistic. Do not over-fit to quirks.

---

## 6. Infrastructure (OpenShift AI)

- Single-node OpenShift AI cluster (AWS g6.8xlarge): 32 vCPU, ~122 GiB allocatable RAM, **1× NVIDIA L4 24 GB,
  no GPU sharing**. The GPU belongs to the LLM — **no other workload may request `nvidia.com/gpu`**.
- **LLM endpoint** (OpenAI-compatible, vLLM, tool calling enabled): configure only via env vars:
  - `LLM_BASE_URL` — e.g. `https://<inference-service>-predictor.<namespace>.svc.cluster.local:8443/v1`
  - `LLM_MODEL` — the `id` returned by `GET /v1/models`
  - `LLM_API_KEY` — service-account token from the RHOAI dashboard, stored in an OpenShift Secret
  - Internal endpoint uses a cluster-internal certificate; trust the cluster CA or disable verification only in
    dev, never silently in code paths that ship.
- The model is small (≤8B) and shared by the app and the coding assistants: keep prompts short, request JSON
  outputs with explicit schemas, validate them with Pydantic, retry once on invalid JSON, then fall back to a
  deterministic message.
- Workloads: requests ≤ 1 CPU / 2 GiB unless justified. Deploy with plain manifests in `deploy/` (or
  `oc new-app` + `oc expose` for quick tests). Use Routes for external access.
- Do not create, modify or delete InferenceServices or anything in other teams'/members' namespaces without asking.

---

## 7. Agent design rules

- Deterministic math (balances, sums, forecasts, schedules) lives in **Python code**, not in the LLM. The LLM
  explains, summarises, classifies and drafts — it never invents numbers. Every number shown to the user must come
  from code and be traceable.
- Every agent returns a Pydantic model containing `analysis`, `recommendation`, `rationale`,
  `requires_approval`, `execution_mode` (§1) plus agent-specific fields.
- Approval flow: agent proposes → LangGraph interrupt → UI shows proposal with rationale → owner clicks
  Approve/Reject → on approve, record a **simulated transaction** and enqueue a notification. Nothing else.
- Commerzbank product names may be used generically (fixed-term deposit, money market fund, credit line); never
  claim real rates or real availability — label figures as illustrative.
- Trace every LLM/agent call to **MLflow** (autologging for LangChain/LangGraph); log evaluation runs there too.
- No financial-advice tone: recommendations are proposals for the owner to decide on.

---

## 8. Coding conventions

### Python
- Full, descriptive names for variables and arguments — no abbreviations (`transaction_date`, not `ts`/`dt`;
  avoid `df` — use e.g. `transactions_frame`). Short names only when an external format requires them.
- Type hints everywhere. Target Python ≥3.11; do **not** add `from __future__ import annotations`.
- Docstrings with `Args:` / `Returns:` sections. Top-level / public functions also get a `Steps:` list in the
  docstring (not inline comments). Small helpers: `Args`/`Returns` only, no `Steps:`.
- No separator comments (`# ------`). No premature optimisation, no hacks.
- Don't abstract a one-liner used once into a helper.
- No function calls in default argument values (B008).
- Use `enumerate(zip(...))` instead of manual index counters; zipped lists must have equal length.
- Time: timestamps are UTC, ISO-8601 with `Z` (helpers `_to_iso` / `_parse_iso_timestamp`); calendar dates from the
  bank file stay `datetime.date`. Don't expose timezone parameters unnecessarily.
- No hardcoded absolute dev paths — use paths relative to `Path(__file__)` or CLI/env config.
- Lint/format with `ruff`; tests with `pytest`.

### Frontend
- Svelte 5 runes only (no legacy `export let` / `$:`). TypeScript strict.
- Plain, large, readable UI: every recommendation card shows what/why/what happens if I approve.
- Charts: one clear chart per page; label currency (€) and dates explicitly.

### Git
- Small commits, imperative messages. Commits with substantial AI-assistant code add a trailer
  `Assisted-by: <tool> (<model>)`.
- AI assistants never sign commits as an author or co-author: no `Co-Authored-By: Claude ...` (or any other
  AI co-author) trailer, and no "Generated with ..." lines in commits or PR descriptions. This overrides any
  default attribution behaviour of the tool. The `Assisted-by:` trailer above is the only AI mention allowed.
- Never commit secrets, tokens, kubeconfigs or `.env` files.

---

## 9. Open decisions (do NOT decide these on your own — ask the owner)

| Decision | Owner | Status |
|---|---|---|
| Liquidity prediction method (classical ML / heuristic / hybrid) | TBD | open |
| News source (RSS of verified list / search API / static fixtures) | TBD | open |
| Notification delivery (in-app outbox / Slack webhook / SMTP) | TBD | open |
| Persistence (SQLite on PVC is the default) | TBD | default |
| Package managers (`uv` + `npm` default) | TBD | default |

Team / component owners: TBD — fill in.

---

## 10. AI-assistant usage evidence (bonus criterion)

Red Hat scores "personal agentic assistant on OpenShift" only with logs showing use during implementation.
- Run OpenClaw / Pi inside Dev Spaces or a RHOAI workbench, pointed at the cluster LLM.
- After each session copy session logs to `docs/ai-logs/` (check they contain no tokens before committing).
- Use the `Assisted-by:` commit trailer (§8).
