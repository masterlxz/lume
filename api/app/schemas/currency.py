from datetime import date, datetime

from pydantic import BaseModel


class CurrencyQuoteResponse(BaseModel):
    pair_code: str
    base_currency: str
    quote_currency: str
    source: str
    cached: bool
    stale: bool
    fetched_at: datetime | None
    price: float

    model_config = {"from_attributes": True}


class CurrencyPriceHistoryPoint(BaseModel):
    price_date: date
    close_price: float

    model_config = {"from_attributes": True}


class CurrencyPriceHistoryResponse(BaseModel):
    pair_code: str
    base_currency: str
    quote_currency: str
    source: str
    cached: bool
    stale: bool
    fetched_at: datetime | None
    data: list[CurrencyPriceHistoryPoint]

    model_config = {"from_attributes": True}
