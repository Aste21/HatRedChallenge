from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel, Field, model_validator

from agent import run_agent


app = FastAPI(title="Instrument Recommendation Agent")


class LockAmount(BaseModel):
    days: int = Field(gt=0)
    amount: float = Field(ge=0, allow_inf_nan=False)
    lowest_balance: float


class ScenarioLimits(BaseModel):
    safe_to_lock: list[LockAmount]

    @model_validator(mode="after")
    def validate_unique_durations(self):
        days = [limit.days for limit in self.safe_to_lock]
        if len(days) != len(set(days)):
            raise ValueError("Each lock duration must appear at most once.")
        return self


class RecommendationRequest(BaseModel):
    account_id: str
    as_of: date
    official: ScenarioLimits
    with_assumptions: ScenarioLimits | None = None


class RecommendationResponse(BaseModel):
    recommendation: str


@app.post("/recommendations", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest) -> RecommendationResponse:
    safe_to_lock_eur = {
        limit.days: limit.amount for limit in request.official.safe_to_lock
    }
    recommendation = run_agent(
        as_of=request.as_of,
        safe_to_lock_eur=safe_to_lock_eur,
    )
    return RecommendationResponse(recommendation=recommendation)