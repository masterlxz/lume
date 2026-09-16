"""B3 "Séries Autorizadas" client — catalog of registered option series.

Public, static file served by B3's CMS (no auth, no Cloudflare gate,
confirmed live in the Fase 1.15 research) — the `fileId` below is the
file's current CMS identifier, not guaranteed permanent if B3 ever
republishes it under a new one:
GET https://www.b3.com.br/lumis/portal/file/fileDownload.jsp?fileId={file_id}

Pipe-delimited text (not fixed-width, confirmed live), one snapshot of the
whole market per download, refreshed by B3 at least daily. Unlike
`cvm_dfp.py`'s permanent per-fiscal-year zip cache, this client always
downloads fresh — no disk cache — because the data itself changes daily
and every underlying's series already live in the same single file, so
there's no per-request fan-out to cache against (the service layer gates
how often this download happens via a global TTL, see
`app/services/options_service.py`).

Two row shapes coexist in the file (confirmed live): type "02" rows are
plain equity/ETF options (call/put on a stock or ETF root code, e.g.
"PETR", "BOVA  FM") — the vast majority (85k of ~87k rows in a live
sample). Type "03" rows are raw stock-index-*points* options (IBOVESPA/
IBOVESPAB3BR/SMALL CAP, cash-settled in R$ per point, a structurally
different column layout). Type "03" is deliberately **out of scope** for
Fase 1.15 — retail exposure to index options is already covered by ETF
options on BOVA11 (an ordinary type "02" row), and the point-settled raw
index contracts are a niche instrument with a different settlement model.
Only type "02" rows are parsed here; anything else is skipped.

Confirmed live: the option series ticker (field 14) always starts with
the exact underlying root code (field 7's first whitespace-separated
token) — verified against all ~85k type "02" rows in a live sample, zero
mismatches. The root code is **not** simply the stock ticker minus its
trailing class digit for every company — e.g. Embraer trades as "EMBR3"
but its option root is "EMBJ" (confirmed live). Same spirit as the CNPJ-
truncation/fund-rename findings already recorded in `project/PENDING.md`:
a known, accepted gap, not solved generically here. Resolving an arbitrary
consumer-facing ticker to its option root is left to the caller for now —
this client exposes the root code as-is as `underlying_symbol`.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime

import requests

SERIES_AUTORIZADAS_URL = (
    "https://www.b3.com.br/lumis/portal/file/fileDownload.jsp"
    "?fileId=8AA8D0CCA023A7E401A0AB1332A3014F"
)
REQUEST_TIMEOUT_SECONDS = 60
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_EQUITY_ROW_TYPE = "02"
_CALL_MARKET_CODE = "70"
_AMERICAN_STYLE_LABEL = "Americano"


class B3OptionsSeriesError(RuntimeError):
    """Raised when the B3 Séries Autorizadas request or parse fails."""


def _parse_row(line: str) -> dict | None:
    fields = line.rstrip("\r\n").split("|")
    if fields[0] != _EQUITY_ROW_TYPE:
        return None

    underlying_symbol = fields[6].strip().split()[0]
    return {
        "series_ticker": fields[13].strip(),
        "underlying_symbol": underlying_symbol,
        "option_type": "CALL" if fields[2] == _CALL_MARKET_CODE else "PUT",
        "strike_price": float(fields[16]),
        "expiration_date": datetime.strptime(fields[17], "%Y%m%d").date(),
        "style": "AMERICAN" if fields[15] == _AMERICAN_STYLE_LABEL else "EUROPEAN",
    }


def fetch_authorized_series() -> list[dict]:
    """Downloads and parses the full market snapshot of registered option
    series. Returns `[{"series_ticker", "underlying_symbol", "option_type",
    "strike_price", "expiration_date", "style"}, ...]` for every stock/ETF
    option series currently registered (~85k, confirmed live) — includes
    series that were never actually traded; cross-reference against
    `b3_cotahist.fetch_latest_option_quotes` to know which ones have a
    real price.
    """
    try:
        response = requests.get(
            SERIES_AUTORIZADAS_URL,
            headers={"User-Agent": _USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            [filename] = zf.namelist()
            text = zf.read(filename).decode("latin-1")
    except (requests.RequestException, zipfile.BadZipFile, IndexError) as exc:
        raise B3OptionsSeriesError(
            f"B3 Séries Autorizadas request/parse failed: {exc}"
        ) from exc

    results = []
    for line in text.splitlines():
        parsed = _parse_row(line)
        if parsed is not None:
            results.append(parsed)
    return results
