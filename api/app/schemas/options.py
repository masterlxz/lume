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
