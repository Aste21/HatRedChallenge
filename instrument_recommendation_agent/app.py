from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class BalancePoint(BaseModel):
    date: date
    balance_pln: int


class RecommendationRequest(BaseModel):
    current_balance_pln: int
    minimum_reserve_pln: int = Field(ge=0)
    forecast: list[BalancePoint] = Field(min_length=1)


@app.post("/recommendations")
def recommend(request: RecommendationRequest):
    lowest_balance = min(
        request.current_balance_pln,
        *(point.balance_pln for point in request.forecast),
    )
    return {
        "provisional_surplus_pln": max(
            0, lowest_balance - request.minimum_reserve_pln
        )
    }
