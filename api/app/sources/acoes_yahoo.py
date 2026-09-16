"""Yahoo Finance unofficial chart API client (quote, price history,
technicals, dividends).

Reimplementation of anchor/data-collector/sources/acoes_yahoo.py's behavior
(see project/CONTEXT.md for the full source catalog this project is
centralizing). Endpoint confirmed live against the real API by the Anchor
project — undocumented (same one `yfinance` uses under the hood), no formal
stability contract, but public and widely used, no key/registration.

GET https://query1.finance.yahoo.com/v8/finance/chart/{ticker}{suffix}
`suffix` is ".SA" for B3 tickers (default) or "" for US/global tickers.

Unlike the Anchor client (which takes a *list* of tickers for a batch
collection job and silently skips ones that fail), this reimplementation
takes a single `ticker` per call — our API serves one ticker per request, so
a failure becomes a request error (`YahooFinanceError`), the same semantics
`app/sources/bcb_sgs.py` already uses for its single series per call.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import requests

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
REQUEST_TIMEOUT_SECONDS = 15

# Covers enough history for 5 complete dividend years (after discarding the
# current, partial year) and the 10y CAGR technical.
HISTORY_RANGE = "10y"
DIVIDENDS_YEARS_AVERAGED = 5

SMA_WINDOWS = (50, 100, 200)
CAGR_YEARS = (5, 10)
SECONDS_PER_YEAR = 365.25 * 86400
# If the closest candle to the target date (today - N years) is farther than
# this, there isn't enough history for that CAGR (e.g. a recent IPO) — None
# is safer than a CAGR computed over the wrong period.
CAGR_ANCHOR_TOLERANCE_DAYS = 30
# Real payment-date-to-candle gaps rarely exceed 1-2 days (weekend/holiday).
DIVIDEND_PRICE_TOLERANCE_DAYS = 5


class YahooFinanceError(RuntimeError):
    """Raised when the Yahoo Finance request or response parsing fails."""


def _fetch_chart(ticker: str, suffix: str, params: dict) -> dict:
    """Shared HTTP + shape handling for all 5 functions below."""
    try:
        response = requests.get(
            f"{YAHOO_CHART_URL}/{ticker}{suffix}",
            params=params,
            headers={"User-Agent": "lume-api/1.0"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["chart"]["result"][0]
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
        raise YahooFinanceError(f"Yahoo Finance request failed for '{ticker}': {exc}") from exc


def fetch_quote(ticker: str, suffix: str = ".SA") -> dict:
    """Current quote. Returns
    `{"price": float, "name": str | None, "exchange": str | None, "currency": str | None}`.
    Only `price` is required — the rest use `.get()` since Yahoo may omit them.
    """
    chart_result = _fetch_chart(ticker, suffix, {"range": "5d", "interval": "1d"})
    try:
        meta = chart_result["meta"]
        price = meta["regularMarketPrice"]
    except (KeyError, TypeError) as exc:
        raise YahooFinanceError(f"Yahoo Finance response missing price for '{ticker}'") from exc

    return {
        "price": price,
        "name": meta.get("longName") or meta.get("shortName"),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "currency": meta.get("currency"),
    }


def fetch_price_history(ticker: str, suffix: str = ".SA") -> list[dict]:
    """Daily closing price for the last 10 years. Returns
    `[{"price_date": date, "close_price": float}, ...]` — one entry per
    trading day (days without a close are skipped).
    """
    chart_result = _fetch_chart(ticker, suffix, {"range": HISTORY_RANGE, "interval": "1d"})
    try:
        timestamps = chart_result["timestamp"]
        closes = chart_result["indicators"]["quote"][0]["close"]
    except (KeyError, TypeError, IndexError) as exc:
        raise YahooFinanceError(f"Yahoo Finance response missing history for '{ticker}'") from exc

    results = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        results.append(
            {
                "price_date": datetime.fromtimestamp(ts, tz=timezone.utc).date(),
                "close_price": close,
            }
        )
    return results


def fetch_dividends_avg(ticker: str, suffix: str = ".SA") -> dict | None:
    """Average dividend per share over the last 5 complete years. Returns
    `{"avg_dividend_5y": float}`, or `None` if the ticker has no dividend
    history covering at least one complete year — a legitimate "no data"
    case, not an error (e.g. growth stocks, recent IPOs).
    """
    chart_result = _fetch_chart(
        ticker, suffix, {"range": HISTORY_RANGE, "interval": "3mo", "events": "div"}
    )
    dividends = chart_result.get("events", {}).get("dividends", {})
    if not dividends:
        return None

    current_year = datetime.now(timezone.utc).year
    yearly_totals: dict[int, float] = defaultdict(float)
    for entry in dividends.values():
        year = datetime.fromtimestamp(entry["date"], tz=timezone.utc).year
        if year == current_year:
            continue
        yearly_totals[year] += entry["amount"]

    complete_years = sorted(yearly_totals, reverse=True)[:DIVIDENDS_YEARS_AVERAGED]
    if not complete_years:
        return None

    avg = sum(yearly_totals[year] for year in complete_years) / len(complete_years)
    return {"avg_dividend_5y": avg}


def _closest_close(
    timestamps: list[int],
    closes: list[float | None],
    target_ts: float,
    tolerance_days: float,
) -> float | None:
    """Closest close to `target_ts`, ignoring non-trading days (`close=None`).
    Returns `None` if the closest candle is farther than `tolerance_days`.
    """
    best_ts, best_close = None, None
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        if best_ts is None or abs(ts - target_ts) < abs(best_ts - target_ts):
            best_ts, best_close = ts, close

    if best_ts is None or abs(best_ts - target_ts) > tolerance_days * 86400:
        return None
    return best_close


def fetch_technicals(ticker: str, suffix: str = ".SA") -> dict:
    """Moving averages (50/100/200d) and CAGR (5/10y). Returns a dict with
    `sma_50`, `sma_100`, `sma_200`, `cagr_5y`, `cagr_10y` — `float` (% for
    CAGR) or `None` when there isn't enough history for that calculation.
    """
    chart_result = _fetch_chart(ticker, suffix, {"range": HISTORY_RANGE, "interval": "1d"})
    try:
        timestamps = chart_result["timestamp"]
        closes = chart_result["indicators"]["quote"][0]["close"]
    except (KeyError, TypeError, IndexError) as exc:
        raise YahooFinanceError(f"Yahoo Finance response missing history for '{ticker}'") from exc

    valid_closes = [c for c in closes if c is not None]
    if not valid_closes:
        raise YahooFinanceError(f"Yahoo Finance returned no trading data for '{ticker}'")

    latest_close = valid_closes[-1]
    latest_ts = timestamps[-1]

    record: dict = {}
    for window in SMA_WINDOWS:
        record[f"sma_{window}"] = (
            sum(valid_closes[-window:]) / window if len(valid_closes) >= window else None
        )

    for years in CAGR_YEARS:
        anchor_close = _closest_close(
            timestamps, closes, latest_ts - years * SECONDS_PER_YEAR, CAGR_ANCHOR_TOLERANCE_DAYS
        )
        if anchor_close is None or anchor_close <= 0:
            record[f"cagr_{years}y"] = None
        else:
            record[f"cagr_{years}y"] = ((latest_close / anchor_close) ** (1 / years) - 1) * 100

    return record


def fetch_dividend_payments(ticker: str, suffix: str = ".SA") -> list[dict]:
    """Full dividend payment history (10 years) with the closing price on
    the payment date. Returns `[{"payment_date": date, "amount": float,
    "price_at_payment": float | None, "yield_pct": float | None}, ...]` —
    empty if the ticker has no dividends in the period (not an error).
    """
    chart_result = _fetch_chart(
        ticker, suffix, {"range": HISTORY_RANGE, "interval": "1d", "events": "div"}
    )
    try:
        timestamps = chart_result["timestamp"]
        closes = chart_result["indicators"]["quote"][0]["close"]
    except (KeyError, TypeError, IndexError) as exc:
        raise YahooFinanceError(f"Yahoo Finance response missing history for '{ticker}'") from exc

    dividends = chart_result.get("events", {}).get("dividends", {})
    if not dividends:
        return []

    results = []
    for entry in dividends.values():
        payment_ts = entry["date"]
        amount = entry["amount"]
        price = _closest_close(timestamps, closes, payment_ts, DIVIDEND_PRICE_TOLERANCE_DAYS)
        results.append(
            {
                "payment_date": datetime.fromtimestamp(payment_ts, tz=timezone.utc).date(),
                "amount": amount,
                "price_at_payment": price,
                "yield_pct": (amount / price * 100) if price else None,
            }
        )
    return results
