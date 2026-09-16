"""Cache-through orchestration for the `rates` domain (Fase 1.13): Meta
Selic diária (BCB SGS) e curva DI futuro/PRE (B3 TaxaSwap).

Ambas reaproveitam `get_or_refresh_list` sem nenhuma modificação — a curva
DI futuro só parece precisar de uma chave composta de 3 colunas
(entidade + data + vértice), mas não tem entidade nenhuma além da própria
data de referência: `reference_date` faz o papel de id_column e
`dias_uteis` o de date_column, exatamente como `reference_year` faz pro
REIT em `us_stock_service.py`.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.rates import DiFuturesCurveVertex, SelicDaily
from app.services.append_only_list_cache import get_or_refresh_list
from app.sources.b3_taxa_swap import B3TaxaSwapError, fetch_pre_curve
from app.sources.bcb_sgs import BcbSgsError, fetch_daily_series
from app.sources.selic_catalog import get_selic_series_info

SELIC_SOURCE_NAME = "bcb_sgs"
DI_FUTURES_SOURCE_NAME = "b3_taxa_swap"


class UnknownSelicSeriesError(ValueError):
    """Raised when `series_code` isn't in the known Selic series catalog."""


class NoCurveDataError(ValueError):
    """Raised when `reference_date` has no DI futures curve data (weekend,
    holiday, or a date not yet published) — distinct from a fetch error."""


def get_or_refresh_selic(db: Session, series_code: str, ttl_seconds: int) -> dict:
    series_info = get_selic_series_info(series_code)
    if series_info is None:
        raise UnknownSelicSeriesError(series_code)

    def _fetch(_id_value):
        return fetch_daily_series(series_info.bcb_code)

    rows, cached, stale = get_or_refresh_list(
        db,
        SelicDaily,
        SelicDaily.series_code,
        series_code,
        SelicDaily.reference_date,
        ttl_seconds,
        _fetch,
        lambda id_value, item, now: {
            "series_code": id_value,
            "reference_date": item["reference_date"],
            "value_pct": item["value_pct"],
            "source": SELIC_SOURCE_NAME,
            "fetched_at": now,
        },
        SELIC_SOURCE_NAME,
        BcbSgsError,
    )
    return {
        "series_code": series_code,
        "source": SELIC_SOURCE_NAME,
        "cached": cached,
        "stale": stale,
        "fetched_at": max((r.fetched_at for r in rows), default=None),
        "data": rows,
    }


def get_or_refresh_di_futures_curve(db: Session, reference_date: date, ttl_seconds: int) -> dict:
    def _fetch(_id_value):
        return fetch_pre_curve(reference_date)

    rows, cached, stale = get_or_refresh_list(
        db,
        DiFuturesCurveVertex,
        DiFuturesCurveVertex.reference_date,
        reference_date,
        DiFuturesCurveVertex.dias_uteis,
        ttl_seconds,
        _fetch,
        lambda id_value, item, now: {
            "reference_date": id_value,
            "dias_uteis": item["dias_uteis"],
            "dias_corridos": item["dias_corridos"],
            "rate_pct": item["rate_pct"],
            "vertice_type": item["vertice_type"],
            "source": DI_FUTURES_SOURCE_NAME,
            "fetched_at": now,
        },
        DI_FUTURES_SOURCE_NAME,
        B3TaxaSwapError,
    )
    if not rows:
        raise NoCurveDataError(reference_date)

    return {
        "reference_date": reference_date,
        "source": DI_FUTURES_SOURCE_NAME,
        "cached": cached,
        "stale": stale,
        "fetched_at": max((r.fetched_at for r in rows), default=None),
        "data": rows,
    }
