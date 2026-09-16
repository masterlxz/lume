"""B3 COTAHIST client — annual end-of-day historical quotes file, filtered
to option series rows (Fase 1.15).

Same "Pesquisa por Pregão"-era legacy public file system already used by
`b3_taxa_swap.py`, a different endpoint:
GET https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP

Confirmed live (Fase 1.15 research): no unauthenticated **daily** file
exists at the naive `COTAHIST_D{ddmmyy}.ZIP` URL some references mention
(B3 answers with a "resource... removed" HTML page, not a zip) — only the
annual file is public this way. For 2026 that's ~80MB compressed / ~700MB
uncompressed, ~2.8M fixed-width 245-byte rows (one row per instrument per
trading day, for the whole year so far). Same reasoning as
`b3_options_series.py` for skipping a disk cache: the service layer
already gates how often this download happens via a global TTL, and it's
downloaded once per refresh regardless of which underlying was requested
— no per-request fan-out to cache against.

Column offsets below are B3's published fixed-width layout, verified live
against real rows (PREULT/PREEXE/DATVEN cross-checked against the same
series in a live `b3_options_series.py` snapshot for the same day —
including a real corporate-action strike adjustment, PETRJ199's strike
moved from 18.80 to 17.61 across trade dates, confirming this file's
`PREEXE` reflects the option's *current* effective strike over time, not
a frozen historical one).

Of the ~2.8M rows, ~2.4M (86%) are option rows (`TPMERC` 070=call/
080=put) — confirmed live that `TOTNEG` (number of trades) is never `0`
on an option row, so a row's mere presence already means "this series
traded that day"; no separate "no trade" filtering is needed.
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from io import BytesIO

import requests

COTAHIST_URL_TEMPLATE = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
REQUEST_TIMEOUT_SECONDS = 180

_CALL_TPMERC = "070"
_PUT_TPMERC = "080"
_OPTION_TPMERC_CODES = (_CALL_TPMERC, _PUT_TPMERC)

# Fixed-width column slices (0-indexed, end-exclusive) per B3's COTAHIST manual.
_CODNEG_SLICE = slice(12, 24)
_TPMERC_SLICE = slice(24, 27)
_PREULT_SLICE = slice(108, 121)
_DATA_SLICE = slice(2, 10)


class B3CotahistError(RuntimeError):
    """Raised when a COTAHIST zip download or parse fails."""


def fetch_latest_option_quotes(year: int) -> dict[str, dict]:
    """Downloads and parses the COTAHIST file for `year`, keeping only the
    most recent traded price per option series ticker — the file carries
    every trading day of the year, but callers only ever need "what did
    this series last trade at". Returns
    `{series_ticker: {"trade_date": date, "close_price": float}}`.
    """
    try:
        response = requests.get(
            COTAHIST_URL_TEMPLATE.format(year=year), timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()

        latest: dict[str, dict] = {}
        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            [filename] = zf.namelist()
            with zf.open(filename) as raw:
                for raw_line in raw:
                    line = raw_line.decode("latin-1")
                    if line[_TPMERC_SLICE] not in _OPTION_TPMERC_CODES:
                        continue

                    series_ticker = line[_CODNEG_SLICE].strip()
                    trade_date = datetime.strptime(line[_DATA_SLICE], "%Y%m%d").date()
                    close_price = int(line[_PREULT_SLICE]) / 100

                    existing = latest.get(series_ticker)
                    if existing is None or trade_date >= existing["trade_date"]:
                        latest[series_ticker] = {
                            "trade_date": trade_date,
                            "close_price": close_price,
                        }
    except (requests.RequestException, zipfile.BadZipFile, ValueError, IndexError) as exc:
        raise B3CotahistError(f"COTAHIST zip download/parse failed for {year}: {exc}") from exc

    return latest
