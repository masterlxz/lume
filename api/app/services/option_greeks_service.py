"""Orchestrates Black-Scholes greeks for one option series (Fase 1.16).

Pure computation over already-cached inputs — no new table, no new
migration, no TTL of its own (a cached greek would always be showing a
stale number, since it depends on the underlying's spot price ticking
constantly; recomputing per request is cheap once the 4 inputs below are
already warm). Reuses:
- `app.services.options_service` (Fase 1.15) for the option's strike/
  expiration/type and last traded price;
- `app.services.stock_service.get_or_refresh_quote` for the underlying's
  spot price — the caller supplies `underlying_ticker` explicitly (e.g.
  "PETR4") rather than the API deriving it from the option's root code,
  since that mapping isn't reliable for every company (Embraer confirmed
  exception, Fase 1.15 / `PENDING.md` P2) and a silently wrong spot price
  would produce a silently wrong greek;
- `app.services.rates_service.get_or_refresh_di_futures_curve` (Fase
  1.13) for the risk-free rate, interpolated at the option's
  days-to-expiry.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.option import OptionEodQuote, OptionSeries
from app.services import black_scholes
from app.services.options_service import (
    refresh_eod_quotes_if_stale,
    refresh_series_catalog_if_stale,
)
from app.services.rates_service import NoCurveDataError, get_or_refresh_di_futures_curve
from app.services.stock_service import get_or_refresh_quote

_DI_CURVE_LOOKBACK_DAYS = 10
_DAYS_PER_YEAR = 365


class OptionSeriesNotFoundError(ValueError):
    """Raised when `series_ticker` isn't a known registered option series."""


class NoMarketPriceError(ValueError):
    """Raised when the series has never actually traded — no EOD price to
    imply a volatility from."""


class OptionExpiredError(ValueError):
    """Raised when the series' expiration date is today or in the past."""


class ImpliedVolatilityNotComputableError(ValueError):
    """Raised when the last traded price is inconsistent with any
    positive volatility (e.g. below intrinsic value) — a stale/unreliable
    market price, not a bug."""


class RiskFreeRateUnavailableError(RuntimeError):
    """Raised when no DI futures curve could be found anywhere in the
    lookback window — all sources failing repeatedly, not just the usual
    weekend/holiday gap."""


def _interpolate_rate(vertices: list, target_dias_corridos: int) -> float:
    """Linear interpolation of `rate_pct` by `dias_corridos` — the option's
    own time-to-expiry uses calendar days too (see `get_option_greeks`),
    so both sides of the interpolation share the same axis without needing
    a business-day calendar. Clamps to the nearest vertex outside the
    published range rather than extrapolating."""
    sorted_vertices = sorted(vertices, key=lambda v: v.dias_corridos)
    if target_dias_corridos <= sorted_vertices[0].dias_corridos:
        return float(sorted_vertices[0].rate_pct)
    if target_dias_corridos >= sorted_vertices[-1].dias_corridos:
        return float(sorted_vertices[-1].rate_pct)

    for lower, upper in zip(sorted_vertices, sorted_vertices[1:]):
        if lower.dias_corridos <= target_dias_corridos <= upper.dias_corridos:
            span = upper.dias_corridos - lower.dias_corridos
            weight = (target_dias_corridos - lower.dias_corridos) / span
            return float(lower.rate_pct) + weight * (float(upper.rate_pct) - float(lower.rate_pct))
    return float(sorted_vertices[-1].rate_pct)  # unreachable given the bounds checks above


def _fetch_recent_di_curve(db: Session, ttl_seconds: int) -> tuple[date, list]:
    reference_date = date.today()
    last_error: Exception | None = None
    for _ in range(_DI_CURVE_LOOKBACK_DAYS):
        try:
            result = get_or_refresh_di_futures_curve(db, reference_date, ttl_seconds)
            return reference_date, result["data"]
        except NoCurveDataError as exc:
            last_error = exc
            reference_date -= timedelta(days=1)
    raise RiskFreeRateUnavailableError(str(last_error))


def get_option_greeks(
    db: Session, series_ticker: str, underlying_ticker: str, settings: Settings
) -> dict:
    series_ticker = series_ticker.upper()
    underlying_ticker = underlying_ticker.upper()

    refresh_series_catalog_if_stale(db, settings.options_ttl_seconds)
    refresh_eod_quotes_if_stale(db, settings.options_ttl_seconds)

    series = db.get(OptionSeries, series_ticker)
    if series is None:
        raise OptionSeriesNotFoundError(series_ticker)

    quote_row = db.get(OptionEodQuote, series_ticker)
    if quote_row is None:
        raise NoMarketPriceError(series_ticker)

    days_to_expiry = (series.expiration_date - date.today()).days
    if days_to_expiry <= 0:
        raise OptionExpiredError(series_ticker)
    years_to_expiry = days_to_expiry / _DAYS_PER_YEAR

    underlying = get_or_refresh_quote(db, underlying_ticker, settings.stock_quote_ttl_seconds)
    spot_price = float(underlying["price"])

    di_reference_date, vertices = _fetch_recent_di_curve(db, settings.cache_ttl_seconds)
    risk_free_rate_pct = _interpolate_rate(vertices, days_to_expiry)
    risk_free_rate = risk_free_rate_pct / 100

    last_price = float(quote_row.close_price)
    strike_price = float(series.strike_price)

    implied_vol = black_scholes.implied_volatility(
        series.option_type, last_price, spot_price, strike_price, years_to_expiry, risk_free_rate
    )
    if implied_vol is None:
        raise ImpliedVolatilityNotComputableError(series_ticker)

    computed_greeks = black_scholes.greeks(
        series.option_type, spot_price, strike_price, years_to_expiry, risk_free_rate, implied_vol
    )

    return {
        "series_ticker": series_ticker,
        "underlying_ticker": underlying_ticker,
        "option_type": series.option_type,
        "strike_price": strike_price,
        "expiration_date": series.expiration_date,
        "spot_price": spot_price,
        "days_to_expiry": days_to_expiry,
        "risk_free_rate_pct": risk_free_rate_pct,
        "di_curve_reference_date": di_reference_date,
        "last_trade_date": quote_row.trade_date,
        "last_price": last_price,
        "implied_volatility_pct": implied_vol * 100,
        "computed_at": datetime.now(timezone.utc),
        **computed_greeks,
    }
