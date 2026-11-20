# SME balance forecast service

Forecasts an SME's account balance for the next days from its bank statement, adjusts the forecast for news,
and says how much cash can safely be locked away (bank deposit, bonds) for 30 / 60 / 90 days.
The product recommender uses the `safe_to_lock` numbers.

## How it works

1. **Statement → transactions in EUR.** Foreign-currency rows use the rate written in the payment reference.
2. **Scheduled payments are detected automatically.** These are rent, payroll, taxes and similar: same counterparty, roughly the same day each month or quarter, at most once a month.
3. **Variable cash is learned from the last 12 normal weeks.** This is everything else (card sales, suppliers). Closed or very quiet weeks are skipped.
4. **4,000 simulated futures.** Each one is built from scheduled payments plus whole weeks drawn at random from that history. Events (from news) change them. The result is a median and a 5–95 % band for every day.
5. **Safe to lock for *d* days = pessimistic lowest balance within *d* days − buffer** (never below 0).
   - The pessimistic lowest balance is the 5th percentile when `risk` = 0.05.
   - The buffer is the cash the user always wants to keep. If it is not given, one month of scheduled payments is suggested.

Nothing is trained or stored in advance: the history is read on every request, and a forecast takes milliseconds.
The only deployed model is the LLM that turns news into events.

## API

Interactive docs are at `/docs` once the service runs.

| Endpoint | Purpose |
|---|---|
| `PUT /accounts/{id}/statement?closing_balance=…&description=…` | Store a statement (CSV body). Returns the row count and date range. |
| `POST /news/events` | `{account_id, news}` → checked `events`, plus `rejected` items with a reason. Calls the LLM. |
| `POST /forecast` | `{account_id, events?, horizon?, current_balance?, risk?, buffer_eur?, lock_days?}` → two scenarios |
| `GET /health` | Health check for OpenShift |

`/forecast` returns two scenarios:
- **`official`**: only events with `certainty: "official"`, meaning confirmed changes with a date and a number. Act on this one.
- **`with_assumptions`**: all events, including estimates such as "sales −5 % because of weak consumer confidence". Show it as a warning or what-if.

Typical flow:

```bash
curl -X POST localhost:8080/news/events -H "Content-Type: application/json" \
     -d '{"account_id": "amalfi", "news": "From 1 Feb 2026 the electricity and gas tariff rises by 15%."}'
# -> {"events": [{"type": "shift_amount", "stream": "City Energy & Utilities AG", "from": "2026-02-01", ...}], ...}

curl -X POST localhost:8080/forecast -H "Content-Type: application/json" \
     -d '{"account_id": "amalfi", "events": [ ...events from above... ], "buffer_eur": 15000}'
```

Event types (checked the same way whether they come from the LLM or from a caller; see [app/events.py](app/events.py)):
`shift_amount` (a scheduled payment changes by x % from a date), `one_off`, `scale` (sales or costs × factor, with uncertainty), `closure`.

## Configuration (environment variables)

| Variable | Meaning | Default |
|---|---|---|
| `LLM_BASE_URL` | OpenAI-compatible base URL of the model, **up to and including `/v1`**. On OpenShift AI this is the inference endpoint of the deployed model (vLLM). | – (required for `/news/events`) |
| `LLM_MODEL` | Served model name (see `curl $LLM_BASE_URL/models`) | – (required for `/news/events`) |
| `LLM_API_KEY` | Bearer token, if token authentication is enabled on the model | empty |
| `LLM_VERIFY_TLS` | `true`, `false` (self-signed cluster certificates) or a path to a CA bundle | `true` |
| `LLM_TIMEOUT_S` | Seconds to wait for the model | `60` |
| `LLM_MAX_TOKENS` | Maximum reply length | `1000` |
| `LLM_JSON_MODE` | Ask the server for JSON output (`response_format`) | `true` |
| `DATA_DIR` | Folder with account data | `data` |

## Run locally

First copy `.env.example` to `.env` and fill in the model URL, name and token.
`.env` is ignored by git and docker, so the token never ends up in the repo or the image.

### With Docker

```bash
docker build -t forecaster .
docker run --rm -p 8080:8080 --env-file .env forecaster    # then open http://localhost:8080/docs
```

Statements uploaded while it runs are lost when the container stops. To keep them, mount the data folder.
In PowerShell use `${PWD}` instead of `$(pwd)`:

```bash
docker run --rm -p 8080:8080 --env-file .env -v "$(pwd)/data:/opt/app-root/src/data" forecaster
```

### Without Docker

```bash
pip install -r requirements-dev.txt python-dotenv   # python-dotenv lets uvicorn read --env-file
pytest -q                                           # 16 tests; the LLM is stubbed
uvicorn app.main:app --reload --port 8080 --env-file .env
```

## Deploy on OpenShift

```bash
oc new-app https://github.com/<org>/<repo> --strategy=docker --name=forecaster
oc create secret generic forecaster-llm --from-literal=LLM_API_KEY=<token>
oc set env deployment/forecaster --from=secret/forecaster-llm
oc set env deployment/forecaster LLM_BASE_URL=<inference endpoint>/v1 LLM_MODEL=<model name>
oc set probe deployment/forecaster --readiness --liveness --get-url=http://:8080/health
oc create route edge --service=forecaster
```

## Data (stand-in for the database)

```
data/accounts/<account_id>/statement.csv   bank statement in the organisers' format
data/accounts/<account_id>/profile.json    {"closing_balance": 33266.35, "description": "..."}
```

`closing_balance` is the balance after the last booking, because the statement has no balance column.
To use the bank API or a database instead, replace `FolderStore` in [app/store.py](app/store.py); nothing else changes.

On OpenShift, uploaded statements are lost when the pod restarts, unless a persistent volume is mounted at `/opt/app-root/src/data`.
The demo account `amalfi` is part of the image.

## Code layout

| File | Contents |
|---|---|
| [app/main.py](app/main.py) | HTTP endpoints, request and response models |
| [app/statement.py](app/statement.py) | CSV → transactions in EUR |
| [app/schedule.py](app/schedule.py) | Automatic detection of scheduled payments |
| [app/forecast.py](app/forecast.py) | Simulation, bands, safe-to-lock, suggested buffer |
| [app/events.py](app/events.py) | Event types and their checks |
| [app/news.py](app/news.py) | Prompt, LLM call, reply → checked events |
| [app/store.py](app/store.py) | Account data (folder for the demo) |
| [app/config.py](app/config.py) | Environment variables |

## Known limits

- **Changes to scheduled payments are picked up late.** A payment whose amount or day changed in the last 3 months is treated as variable cash until it has repeated 3 times. The same applies to a monthly payment that skipped a month.
- **No trend or seasonality.** The forecast assumes the next weeks look like the last 12 normal weeks, so the band is narrower than the real uncertainty over 90 days.
- **Payments that end are not recognised.** A payment that will stop is still forecast, unless an event or a new statement says otherwise. Example: the CHF wire in the demo data is "tranche 12/12" in December.
