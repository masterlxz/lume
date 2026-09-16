from datetime import date, datetime

from pydantic import BaseModel


class SelicPoint(BaseModel):
    reference_date: date
    value_pct: float

    model_config = {"from_attributes": True}


class SelicResponse(BaseModel):
    series_code: str
    source: str
    cached: bool
    stale: bool
    fetched_at: datetime | None
    data: list[SelicPoint]

    model_config = {"from_attributes": True}


class DiFuturesCurvePoint(BaseModel):
    dias_corridos: int
    dias_uteis: int
    rate_pct: float
    vertice_type: str

    model_config = {"from_attributes": True}


class DiFuturesCurveResponse(BaseModel):
    reference_date: date
    source: str
    cached: bool
    stale: bool
    fetched_at: datetime | None
    data: list[DiFuturesCurvePoint]

    model_config = {"from_attributes": True}
