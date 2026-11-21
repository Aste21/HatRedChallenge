"""HTTP API. Run locally with:  uvicorn app.main:app --reload --port 8080   (interactive docs at /docs)

Typical flow:
  1. PUT  /accounts/{id}/statement   store a bank statement (once, or whenever new bookings arrive)
  2. POST /news/events               news text -> checked events (calls the LLM)
  3. POST /forecast                  account + events -> balance bands and safe-to-lock, two scenarios:
                                     'official' (only confirmed events) and 'with_assumptions' (all events)
"""
import datetime as dt
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import Settings, load_settings
from .events import Event, unknown_streams
from .forecast import History, NotEnoughHistory, Scenario, build_history, run_scenario
from .news import LLMError, ask_llm, business_context, events_from_reply
from .schedule import Payment, detect_schedule
from .statement import StatementError, read_statement
from .store import ACCOUNT_ID, AccountNotFound, FolderStore

app = FastAPI(title="SME balance forecast", version="1.0.0",
              description="Forecasts an SME's account balance from its statement history and news events, "
                          "and says how much cash can safely be locked away (deposit, bonds).")

_settings = load_settings()


def get_settings() -> Settings:
    return _settings


def get_store(settings: Settings = Depends(get_settings)) -> FolderStore:
    return FolderStore(settings.data_dir)


# --- loading an account --------------------------------------------------------------------------------

@dataclass
class Account:
    history: History
    schedule: list[Payment]
    closing_balance: float | None
    description: str


def load_account(store: FolderStore, account_id: str) -> Account:
    """Read the stored statement, detect scheduled payments and build the daily history."""
    try:
        raw, profile = store.load(account_id)
    except AccountNotFound:
        raise HTTPException(404, f"account {account_id!r} not found") from None
    try:
        tx = read_statement(raw)
    except StatementError as exc:
        raise HTTPException(422, f"stored statement cannot be read: {exc}") from None
    schedule, is_scheduled = detect_schedule(tx)
    return Account(history=build_history(tx, is_scheduled), schedule=schedule,
                   closing_balance=profile.get("closing_balance"), description=profile.get("description", ""))


AccountId = Annotated[str, Field(pattern=ACCOUNT_ID.pattern, examples=["amalfi"])]


# --- PUT /accounts/{id}/statement ----------------------------------------------------------------------

class UploadResult(BaseModel):
    account_id: str
    transactions: int
    first_date: dt.date
    last_date: dt.date
    closing_balance: float


@app.put("/accounts/{account_id}/statement", response_model=UploadResult,
         openapi_extra={"requestBody": {"required": True, "content": {"text/csv": {"schema": {"type": "string"}}}}})
async def upload_statement(
    request: Request,
    account_id: str = Path(pattern=ACCOUNT_ID.pattern),
    closing_balance: float = Query(description="balance after the last booking in the file, EUR"),
    description: str | None = Query(None, description="one line about the business, e.g. 'Bakery in Munich'"),
    store: FolderStore = Depends(get_store),
):
    """Store a bank statement (CSV as the request body). Replaces the account's previous statement."""
    raw = await request.body()
    try:
        tx = read_statement(raw)
    except StatementError as exc:
        raise HTTPException(400, str(exc)) from None
    store.save(account_id, raw, closing_balance, description)
    return UploadResult(account_id=account_id, transactions=len(tx), first_date=tx["date"].min().date(),
                        last_date=tx["date"].max().date(), closing_balance=closing_balance)


# --- POST /forecast ------------------------------------------------------------------------------------

class ForecastRequest(BaseModel):
    # a working example for Swagger's "Try it out" (the generated one would use the stream name "string")
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "account_id": "amalfi",
        "events": [
            {"type": "shift_amount", "stream": "City Energy & Utilities AG", "from": "2026-02-01",
             "change_pct": 15, "certainty": "official", "why": "supplier letter: tariff +15% from 1 Feb"},
            {"type": "scale", "flow": "sales", "from": "2026-01-12", "to": "2026-01-25",
             "factor_mean": 0.6, "factor_sd": 0.1, "certainty": "assumption", "why": "road works on the street"},
        ],
        "horizon": 90,
        "lock_days": [30, 60, 90],
    }]})

    account_id: AccountId
    events: list[Event] = Field(default_factory=list, description="usually the output of /news/events")
    horizon: int = Field(90, ge=7, le=365, description="days to forecast")
    current_balance: float | None = Field(None, description="EUR; defaults to the stored closing balance")
    risk: float = Field(0.05, gt=0, lt=0.5, description="share of simulated futures allowed to dip into the buffer")
    buffer_eur: float | None = Field(None, ge=0, description="cash to keep at all times; "
                                                             "if omitted, one month of scheduled payments is suggested")
    lock_days: list[int] = Field(default_factory=lambda: [30, 60, 90], description="lock periods to price")

    @model_validator(mode="after")
    def _lock_days_within_horizon(self):
        if not self.lock_days or any(not 1 <= d <= self.horizon for d in self.lock_days):
            raise ValueError("lock_days must be between 1 and horizon")
        return self


class ForecastResponse(BaseModel):
    account_id: str
    as_of: dt.date                 # last booked day; the forecast starts the day after
    start_balance: float
    schedule: list[Payment]        # scheduled payments found in the statement
    official: Scenario             # only events with certainty "official"
    with_assumptions: Scenario     # all events


@app.post("/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest, store: FolderStore = Depends(get_store)):
    """Forecast the balance and the safe-to-lock amounts, for official events only and for all events."""
    acc = load_account(store, req.account_id)

    unknown = unknown_streams(req.events, {p.name for p in acc.schedule})
    if unknown:
        raise HTTPException(422, f"unknown scheduled payments in events: {unknown}")

    start = req.current_balance if req.current_balance is not None else acc.closing_balance
    if start is None:
        raise HTTPException(422, "no closing balance stored for this account; send current_balance")

    def scenario(events: list[Event]) -> Scenario:
        return run_scenario(acc.history, acc.schedule, start, events, req.horizon, req.risk,
                            req.buffer_eur, req.lock_days)

    try:
        official = scenario([e for e in req.events if e.certainty == "official"])
        with_assumptions = scenario(req.events)
    except NotEnoughHistory as exc:
        raise HTTPException(422, str(exc)) from None

    return ForecastResponse(account_id=req.account_id, as_of=acc.history.origin.date(), start_balance=start,
                            schedule=acc.schedule, official=official, with_assumptions=with_assumptions)


# --- POST /news/events ---------------------------------------------------------------------------------

class NewsRequest(BaseModel):
    account_id: AccountId
    news: str = Field(min_length=1, max_length=5000, examples=[
        "Your energy supplier writes: from 1 Feb 2026 the electricity and gas tariff rises by 15%."])


class Rejected(BaseModel):
    event: Any
    reason: str


class NewsResponse(BaseModel):
    account_id: str
    events: list[Event]            # checked events, ready to send to /forecast
    rejected: list[Rejected]       # what the model proposed but failed the checks


@app.post("/news/events", response_model=NewsResponse)
def news_events(req: NewsRequest, store: FolderStore = Depends(get_store),
                settings: Settings = Depends(get_settings)):
    """Turn one news item into events for this account, using the LLM. Only checked events are returned."""
    if not settings.llm_configured:
        raise HTTPException(503, "the news model is not configured (set LLM_BASE_URL and LLM_MODEL)")
    acc = load_account(store, req.account_id)
    context = business_context(acc.description, acc.schedule, acc.history.origin.date().isoformat())
    try:
        reply = ask_llm(settings, req.news, context)
        events, rejected = events_from_reply(reply, {p.name for p in acc.schedule})
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from None
    return NewsResponse(account_id=req.account_id, events=events, rejected=rejected)


@app.get("/health")
def health():
    """Liveness/readiness probe for OpenShift."""
    return {"status": "ok"}
