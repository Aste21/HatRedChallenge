from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.forecasting.client import Forecast, ForecastClient, get_forecast_client
from app.service_client import ServiceUnavailableError

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("", response_model=Forecast)
def get_forecast(
    forecast_client: Annotated[ForecastClient, Depends(get_forecast_client)],
    horizon: Annotated[int, Query(ge=7, le=365)] = 90,
) -> Forecast:
    """Balance forecast with daily bands and safe-to-lock amounts, from the forecast service.

    Args:
        forecast_client: Injected forecast client.
        horizon: Number of days to forecast.

    Returns:
        The forecast.
    """
    try:
        return forecast_client.fetch_forecast(horizon)
    except ServiceUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
