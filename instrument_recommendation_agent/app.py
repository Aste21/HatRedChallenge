from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel, Field, model_validator

from agent import run_agent


app = FastAPI(title="Instrument Recommendation Agent")


class BalancePoint(BaseModel):
    date: date
    balance_pln: int


class RecommendationRequest(BaseModel):
    as_of: date
    current_balance_pln: int
    minimum_reserve_pln: int = Field(ge=0)
    forecast: list[BalancePoint] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_forecast_dates(self):
        dates = [point.date for point in self.forecast]

        if any(day < self.as_of for day in dates):
            raise ValueError("Forecast dates must be on or after as_of.")

        if len(dates) != len(set(dates)):
            raise ValueError("Forecast dates must be unique.")

        return self


class RecommendationResponse(BaseModel):
    recommendation: str


@app.post("/recommendations", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest) -> RecommendationResponse:
    recommendation = run_agent(
        as_of=request.as_of,
        current_balance_pln=request.current_balance_pln,
        minimum_reserve_pln=request.minimum_reserve_pln,
        forecast={point.date: point.balance_pln for point in request.forecast},
    )
    return RecommendationResponse(recommendation=recommendation)
