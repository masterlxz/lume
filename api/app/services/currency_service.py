"""Cache-through orchestration for FX cross-rate quotes/price history.

Reuses app.sources.acoes_yahoo directly (currency pairs are just Yahoo
Finance quotes for a "{BASE}{QUOTE}=X" ticker, mechanically derived from
the pair code — see app/sources/currency_catalog.py) — no dedicated HTTP
client for this domain, same reuse pattern as app/services/metal_service.py.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.currency import CurrencyPriceHistory, CurrencyQuote
from app.services.append_only_list_cache import get_or_refresh_list
from app.services.single_row_cache import get_or_refresh_single_row
from app.sources.acoes_yahoo import YahooFinanceError, fetch_price_history, fetch_quote
from app.sources.currency_catalog import resolve_pair

SOURCE_NAME = "yahoo_finance"


class UnknownCurrencyPairError(ValueError):
    """Raised when `pair_code` isn't two distinct, known currencies."""


def _yahoo_ticker(base: str, quote: str) -> str:
    return f"{base}{quote}=X".upper()


def get_or_refresh_quote(db: Session, pair_code: str, ttl_seconds: int) -> dict:
    pair_code = pair_code.lower()
    resolved = resolve_pair(pair_code)
    if resolved is None:
        raise UnknownCurrencyPairError(pair_code)
    base, quote = resolved

    def _fetch(_code):
        result = fetch_quote(_yahoo_ticker(base, quote), suffix="")
        return {"price": result["price"]}

    row, cached, stale = get_or_refresh_single_row(
        db, CurrencyQuote, CurrencyQuote.pair_code, pair_code, ttl_seconds, _fetch, SOURCE_NAME,
        YahooFinanceError,
    )
    return {
        "pair_code": pair_code,
        "base_currency": base,
        "quote_currency": quote,
        "source": SOURCE_NAME,
        "cached": cached,
        "stale": stale,
        "fetched_at": row.fetched_at,
        "price": row.price,
    }


def get_or_refresh_price_history(db: Session, pair_code: str, ttl_seconds: int) -> dict:
    pair_code = pair_code.lower()
    resolved = resolve_pair(pair_code)
    if resolved is None:
        raise UnknownCurrencyPairError(pair_code)
    base, quote = resolved

    rows, cached, stale = get_or_refresh_list(
        db,
        CurrencyPriceHistory,
        CurrencyPriceHistory.pair_code,
        pair_code,
        CurrencyPriceHistory.price_date,
        ttl_seconds,
        lambda _code: fetch_price_history(_yahoo_ticker(base, quote), suffix=""),
        lambda code, item, now: {
            "pair_code": code,
            "price_date": item["price_date"],
            "close_price": item["close_price"],
            "source": SOURCE_NAME,
            "fetched_at": now,
        },
        SOURCE_NAME,
        YahooFinanceError,
    )
    return {
        "pair_code": pair_code,
        "base_currency": base,
        "quote_currency": quote,
        "source": SOURCE_NAME,
        "cached": cached,
        "stale": stale,
        "fetched_at": max((r.fetched_at for r in rows), default=None),
        "data": rows,
    }
