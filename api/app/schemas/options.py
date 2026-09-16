from datetime import date, datetime

from pydantic import BaseModel


class OptionSeriesPoint(BaseModel):
    series_ticker: str
    option_type: str
    strike_price: float
    expiration_date: date
    style: str
    last_price: float | None
    last_trade_date: date | None

    model_config = {"from_attributes": True}


class OptionSeriesResponse(BaseModel):
    underlying_symbol: str
    source: str
    cached: bool
    stale: bool
    fetched_at: datetime | None
    data: list[OptionSeriesPoint]

    model_config = {"from_attributes": True}


class OptionGreeksResponse(BaseModel):
    series_ticker: str
    underlying_ticker: str
    option_type: str
    strike_price: float
    expiration_date: date
    spot_price: float
    days_to_expiry: int
    risk_free_rate_pct: float
    di_curve_reference_date: date
    last_trade_date: date
    last_price: float
    implied_volatility_pct: float
    delta: float
    gamma: float
    theta: float
    vega: float
    computed_at: datetime

    model_config = {"from_attributes": True}
