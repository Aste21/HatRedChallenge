from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from agent import (
    InvalidRecommendationError,
    NotificationDraft,
    RecommendedFamily,
    request_decision,
    run_agent,
)
from tools import OFFERS



app = FastAPI(title="Instrument Recommendation Agent")
app.state.request_decision = request_decision


class LockAmount(BaseModel):
    days: int = Field(gt=0)
    amount: Decimal = Field(ge=0, allow_inf_nan=False)
    lowest_balance: float


class ScenarioLimits(BaseModel):
    safe_to_lock: list[LockAmount]

    @model_validator(mode="after")
    def validate_unique_durations(self):
        durations = [limit.days for limit in self.safe_to_lock]
        if len(durations) != len(set(durations)):
            raise ValueError("Each lock duration must appear at most once.")
        return self


class RecommendationRequest(BaseModel):
    account_id: str
    as_of: date
    official: ScenarioLimits
    with_assumptions: ScenarioLimits | None = None


class RecommendationResponse(BaseModel):
    account_id: str
    as_of: date
    families: list[RecommendedFamily] = Field(max_length=3)
    notification: NotificationDraft


class OfferTermsResponse(BaseModel):
    term_days: list[int]


@app.get("/offer-terms", response_model=OfferTermsResponse)
def offer_terms() -> OfferTermsResponse:
    return OfferTermsResponse(
        term_days=sorted(
            {offer["term_days"] for offer in OFFERS.values() if "term_days" in offer}
        )
    )


@app.post("/recommendations", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest) -> RecommendationResponse:
    safe_to_lock_eur = {
        limit.days: limit.amount for limit in request.official.safe_to_lock
    }

    try:
        families, notification = run_agent(
            as_of=request.as_of,
            decide=app.state.request_decision,
            safe_to_lock_eur=safe_to_lock_eur,
        )
    except InvalidRecommendationError as error:
        raise HTTPException(
            status_code=502,
            detail="The recommendation model returned an invalid selection.",
        ) from error


    return RecommendationResponse(
        account_id=request.account_id,
        as_of=request.as_of,
        families=families,
        notification=notification,
    )
