"""Cache-through orchestration for the B3 option series catalog + EOD
quotes (Fase 1.15).

Unlike every other domain, the two sources here (`b3_options_series`,
`b3_cotahist`) don't fetch by identifier — each call returns the *entire*
market's data in one shot, so `single_row_cache`/`append_only_list_cache`
(both built around "fetch for this one id") don't fit. Freshness is
tracked globally (`MAX(fetched_at)` across the whole table, not per
`underlying_symbol`), and a stale check triggers a full-table refresh:
delete-and-reinsert for the series catalog (same reasoning as
`FiiProperty` — a de-registered series must disappear, not linger), bulk
upsert for EOD quotes (a past close price never changes, but a series can
gain a fresher one). Whatever underlying was actually requested is served
by a plain `SELECT ... WHERE` afterward — an unknown/optionless
`underlying_symbol` is a legitimate empty result, not an error (same
reasoning as `/v1/fiis/{cnpj}/properties`).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.models.option import OptionEodQuote, OptionSeries
from app.services.db_dialect import upsert_insert
from app.services.freshness import is_fresh
from app.sources.b3_cotahist import B3CotahistError, fetch_latest_option_quotes
from app.sources.b3_options_series import B3OptionsSeriesError, fetch_authorized_series

logger = logging.getLogger(__name__)

SERIES_SOURCE_NAME = "b3_series_autorizadas"
QUOTES_SOURCE_NAME = "b3_cotahist"
SOURCE_NAME = f"{SERIES_SOURCE_NAME}+{QUOTES_SOURCE_NAME}"

_UPSERT_CHUNK_SIZE = 5000


def refresh_series_catalog_if_stale(db: Session, ttl_seconds: int) -> tuple[bool, bool]:
    """Returns `(refreshed, stale)`. Public — also called directly by
    `option_greeks_service.py` (Fase 1.16), which needs the same global
    refresh but reads a single series by ticker instead of listing by
    `underlying_symbol`."""
    latest_fetched_at = db.scalar(select(func.max(OptionSeries.fetched_at)))
    if is_fresh(latest_fetched_at, ttl_seconds):
        return False, False

    try:
        items = fetch_authorized_series()
    except B3OptionsSeriesError:
        if latest_fetched_at is None:
            raise
        logger.warning("%s unavailable, serving stale option series catalog", SERIES_SOURCE_NAME)
        return False, True

    now = datetime.now(timezone.utc)
    rows = [
        {
            "series_ticker": item["series_ticker"],
            "underlying_symbol": item["underlying_symbol"],
            "option_type": item["option_type"],
            "strike_price": item["strike_price"],
            "expiration_date": item["expiration_date"],
            "style": item["style"],
            "source": SERIES_SOURCE_NAME,
            "fetched_at": now,
        }
        for item in items
    ]

    db.execute(delete(OptionSeries))
    for start in range(0, len(rows), _UPSERT_CHUNK_SIZE):
        chunk = rows[start : start + _UPSERT_CHUNK_SIZE]
        if chunk:
            db.execute(insert(OptionSeries), chunk)
    db.commit()
    return True, False


def refresh_eod_quotes_if_stale(db: Session, ttl_seconds: int) -> tuple[bool, bool]:
    """Returns `(refreshed, stale)`. Public — see
    `refresh_series_catalog_if_stale` above."""
    latest_fetched_at = db.scalar(select(func.max(OptionEodQuote.fetched_at)))
    if is_fresh(latest_fetched_at, ttl_seconds):
        return False, False

    try:
        quotes_by_ticker = fetch_latest_option_quotes(date.today().year)
    except B3CotahistError:
        if latest_fetched_at is None:
            raise
        logger.warning("%s unavailable, serving stale option EOD quotes", QUOTES_SOURCE_NAME)
        return False, True

    now = datetime.now(timezone.utc)
    rows = [
        {
            "series_ticker": series_ticker,
            "trade_date": item["trade_date"],
            "close_price": item["close_price"],
            "source": QUOTES_SOURCE_NAME,
            "fetched_at": now,
        }
        for series_ticker, item in quotes_by_ticker.items()
    ]

    insert_fn = upsert_insert(db.get_bind())
    for start in range(0, len(rows), _UPSERT_CHUNK_SIZE):
        chunk = rows[start : start + _UPSERT_CHUNK_SIZE]
        if not chunk:
            continue
        stmt = insert_fn(OptionEodQuote).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[OptionEodQuote.series_ticker],
            set_={
                "trade_date": stmt.excluded.trade_date,
                "close_price": stmt.excluded.close_price,
                "source": stmt.excluded.source,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        db.execute(stmt)
    db.commit()
    return True, False


def _root_code(ticker: str) -> str:
    """B3's option root code is the ticker without its trailing class
    digit(s) (e.g. "PETR4" -> "PETR", "BOVA11" -> "BOVA") for the
    overwhelming majority of names — confirmed live against ~85k series
    (Fase 1.15 research). Known, accepted exception: Embraer trades as
    "EMBR3" but its option root is "EMBJ" (a B3 naming quirk, not derivable
    from the ticker) — same spirit as the CNPJ-truncation/fund-rename gaps
    already recorded in `project/PENDING.md`, not solved generically here.
    """
    return ticker.upper().rstrip("0123456789")


def get_series_with_last_quote(db: Session, underlying_symbol: str, ttl_seconds: int) -> dict:
    root_code = _root_code(underlying_symbol)

    series_refreshed, series_stale = refresh_series_catalog_if_stale(db, ttl_seconds)
    quotes_refreshed, quotes_stale = refresh_eod_quotes_if_stale(db, ttl_seconds)

    series_rows = db.scalars(
        select(OptionSeries)
        .where(OptionSeries.underlying_symbol == root_code)
        .order_by(OptionSeries.expiration_date, OptionSeries.strike_price)
    ).all()

    quotes_by_ticker = {}
    if series_rows:
        quotes_by_ticker = {
            q.series_ticker: q
            for q in db.scalars(
                select(OptionEodQuote).where(
                    OptionEodQuote.series_ticker.in_([s.series_ticker for s in series_rows])
                )
            ).all()
        }

    data = [
        {
            "series_ticker": s.series_ticker,
            "option_type": s.option_type,
            "strike_price": s.strike_price,
            "expiration_date": s.expiration_date,
            "style": s.style,
            "last_price": quotes_by_ticker[s.series_ticker].close_price
            if s.series_ticker in quotes_by_ticker
            else None,
            "last_trade_date": quotes_by_ticker[s.series_ticker].trade_date
            if s.series_ticker in quotes_by_ticker
            else None,
        }
        for s in series_rows
    ]

    return {
        "underlying_symbol": root_code,
        "source": SOURCE_NAME,
        "cached": not (series_refreshed or quotes_refreshed),
        "stale": series_stale or quotes_stale,
        "fetched_at": max((s.fetched_at for s in series_rows), default=None),
        "data": data,
    }
