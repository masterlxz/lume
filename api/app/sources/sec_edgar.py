"""SEC EDGAR client (US fundamentals, equivalent of the CVM for DCF/FCFF).

Reimplementation of anchor/data-collector/sources/sec_edgar.py's behavior
(see project/CONTEXT.md for the full source catalog). Free, no key — only
requires a `User-Agent` header with a contact email (their policy, not real
authentication: https://www.sec.gov/os/webmaster-faq#developers), and
respects a ~10 req/s ceiling.

Unlike the CVM (one zip per year, numeric account codes), the SEC exposes
XBRL per company: `GET /api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json`
returns the **full history** of one tag (`Revenues`, `NetIncomeLoss`, ...)
in a single call — including the current and prior fiscal year for the same
concept, which removes the need for a second request for `nwc_change` (the
CVM needs ÚLTIMO/PENÚLTIMO from the same annual file; here they already
come together in the same response).

**Critical finding (confirmed live against Apple)**: filtering only by
`form == "10-K"` and `fp == "FY"` isn't enough for duration concepts (ones
with a `start` field). Apple uses the same tag in the 10-K's "selected
quarterly data" footnotes — `Revenues`/`PaymentsOfDividendsCommonStock` came
back with mostly short-duration (quarter/9-month) rows even with correct
`form`/`fp`. Fix: also require the `end - start` window to be 350-380 days
before accepting a row as annual. Instant concepts (no `start`, e.g.
`StockholdersEquity`) don't need this extra filter.

**Restatement (10-K/A)**: more than one row can share the same `end` (a
correction re-files the same period) — tie-broken by the most recent
`filed`, not the first one seen.

**Bank taxonomy gap** (mirrors the same CVM finding for banks/COSIF):
against JPMorgan, `OperatingIncomeLoss`, `InventoryNet`,
`AccountsReceivableNetCurrent`, `AccountsPayableCurrent`,
`PaymentsToAcquirePropertyPlantAndEquipment`, `LongTermDebtNoncurrent` and
the revenue tags all 404 — banks don't report EBIT/inventory/receivables-
payables/capex/contract-revenue the way non-financial companies do.
`fetch_dcf_fundamentals` returns `None` for those tickers (same spirit as
CVM's `LookupError`); `fetch_fundamentals` (LPA/VPA/ROE) keeps working since
it doesn't depend on those tags.

**Scale**: every aggregated monetary field (EBIT, D&A, Capex, the 3 ΔNWC
legs, debt, cash, revenue, inventory) is returned in **millions of dollars**
— same convention as `cvm_dfp.py`'s `_to_millions_brl`. LPA/VPA/ROE/tax rate
(ratios) aren't scaled.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Callable

import requests

EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
EDGAR_CONCEPT_URL_TEMPLATE = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"
)
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "sec_edgar"
TICKERS_CACHE_PATH = CACHE_DIR / "company_tickers.json"
REQUEST_TIMEOUT_SECONDS = 15

# `company_tickers.json` has no version in its name (unlike the CVM zip,
# whose name always carries the year) — an eternal cache would leave a new
# IPO unresolvable forever. Short TTL is the deliberate deviation from
# `cvm_dfp._resolve_zip_path`'s idiom.
TICKERS_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60

REQUEST_INTERVAL_SECONDS = 0.11  # ~9 req/s, under the SEC's 10 req/s ceiling
PAYOUT_YEARS_AVERAGED = 5

_MAX_PLAUSIBLE_TAX_RATE = 100.0
_ANNUAL_DURATION_MIN_DAYS = 350
_ANNUAL_DURATION_MAX_DAYS = 380
DIVIDEND_TAGS = ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"]

# Single global timestamp shared by every call through `_get()` — same
# simplification already present in the Anchor project's own
# implementation. Not thread-safe under concurrent requests (FastAPI runs
# sync routes in a threadpool); acceptable at MVP traffic levels, see
# project/ARCHITECTURE.md — not resolved with a lock here.
_last_request_at = 0.0


class SecEdgarError(RuntimeError):
    """Raised when a SEC EDGAR request or response parsing fails, or when
    no contact email is configured."""


def _headers(contact_email: str) -> dict:
    return {"User-Agent": f"lume-api ({contact_email})"}


def _get(url: str, contact_email: str) -> requests.Response:
    """Every network call goes through here — keeps the rate limit in one
    place."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < REQUEST_INTERVAL_SECONDS:
        time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
    try:
        response = requests.get(
            url, headers=_headers(contact_email), timeout=REQUEST_TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise SecEdgarError(f"SEC EDGAR request failed: {exc}") from exc
    finally:
        _last_request_at = time.monotonic()
    return response


def _download_tickers(contact_email: str) -> Path:
    if (
        TICKERS_CACHE_PATH.exists()
        and time.time() - TICKERS_CACHE_PATH.stat().st_mtime < TICKERS_CACHE_TTL_SECONDS
    ):
        return TICKERS_CACHE_PATH

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    response = _get(EDGAR_TICKERS_URL, contact_email)
    try:
        response.raise_for_status()
        TICKERS_CACHE_PATH.write_bytes(response.content)
    except requests.RequestException as exc:
        raise SecEdgarError(f"SEC EDGAR ticker list download failed: {exc}") from exc
    return TICKERS_CACHE_PATH


def resolve_cik(ticker: str, contact_email: str) -> int | None:
    """Resolves `ticker` to its SEC CIK. Returns `None` if not found — not
    an error."""
    if not contact_email:
        raise SecEdgarError("SEC_EDGAR_CONTACT_EMAIL is not configured")

    path = _download_tickers(contact_email)
    try:
        entries = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SecEdgarError(f"SEC EDGAR ticker list parse failed: {exc}") from exc

    ticker_upper = ticker.upper()
    for entry in entries.values():
        if entry["ticker"].upper() == ticker_upper:
            return entry["cik_str"]
    return None


def _fetch_concept(cik: int, tag: str, contact_email: str) -> list[dict] | None:
    """Rows of `units` for this tag (`USD`, `USD/shares` or `shares` — the
    key varies by tag, tries all three). `None` if the company doesn't
    report this tag (404 — expected for banks on several fields)."""
    response = _get(EDGAR_CONCEPT_URL_TEMPLATE.format(cik=cik, tag=tag), contact_email)
    if response.status_code == 404:
        return None
    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SecEdgarError(
            f"SEC EDGAR concept request failed for CIK {cik}/{tag}: {exc}"
        ) from exc

    units = payload.get("units", {})
    for unit_key in ("USD", "USD/shares", "shares"):
        if unit_key in units:
            return units[unit_key]
    return None


def _is_annual_duration(row: dict) -> bool:
    if "start" not in row:
        return True
    start = date.fromisoformat(row["start"])
    end = date.fromisoformat(row["end"])
    days = (end - start).days
    return _ANNUAL_DURATION_MIN_DAYS <= days <= _ANNUAL_DURATION_MAX_DAYS


def _annual_rows(rows: list[dict]) -> list[dict]:
    return [
        r for r in rows if r.get("form") == "10-K" and r.get("fp") == "FY" and _is_annual_duration(r)
    ]


def _latest_duration(rows: list[dict]) -> dict | None:
    candidates = _annual_rows(rows)
    if not candidates:
        return None
    max_end = max(r["end"] for r in candidates)
    same_end = [r for r in candidates if r["end"] == max_end]
    return max(same_end, key=lambda r: r["filed"])


def _latest_instant(rows: list[dict], rank: int = 0) -> dict | None:
    """`rank=0` is the most recent fiscal year, `rank=1` the prior one (for
    `nwc_change`)."""
    candidates = _annual_rows(rows)
    if not candidates:
        return None
    ends = sorted({r["end"] for r in candidates}, reverse=True)
    if rank >= len(ends):
        return None
    same_end = [r for r in candidates if r["end"] == ends[rank]]
    return max(same_end, key=lambda r: r["filed"])


def _try_tags(
    cik: int, tags: list[str], picker: Callable[[list[dict]], dict | None], contact_email: str
) -> dict | None:
    """Tries each candidate tag and returns the most recent row **among all
    that resolved**, not the first tag with any data — a tag can have real
    data that stops years before a newer tag covering the same concept."""
    candidates = []
    for tag in tags:
        rows = _fetch_concept(cik, tag, contact_email)
        if rows is None:
            continue
        row = picker(rows)
        if row is not None:
            candidates.append(row)
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r["end"], r["filed"]))


def _required(
    cik: int, tags: list[str], picker: Callable[[list[dict]], dict | None], contact_email: str
) -> float:
    row = _try_tags(cik, tags, picker, contact_email)
    if row is None:
        raise LookupError(f"none of tags {tags!r} found for CIK {cik}")
    return row["val"]


def _optional(
    cik: int, tags: list[str], picker: Callable[[list[dict]], dict | None], contact_email: str
) -> float | None:
    row = _try_tags(cik, tags, picker, contact_email)
    return None if row is None else row["val"]


def _to_millions(val: float) -> float:
    return val / 1_000_000


def _to_millions_or_none(val: float | None) -> float | None:
    return None if val is None else _to_millions(val)


def _required_instant_at(cik: int, tag: str, rank: int, contact_email: str) -> float:
    rows = _fetch_concept(cik, tag, contact_email)
    if rows is None:
        raise LookupError(f"tag {tag!r} not found for CIK {cik}")
    row = _latest_instant(rows, rank)
    if row is None:
        raise LookupError(f"tag {tag!r} has no rank {rank} fiscal year for CIK {cik}")
    return row["val"]


def _nwc_change(cik: int, contact_email: str) -> float:
    def nwc_at(rank: int) -> float:
        receivables = _required_instant_at(cik, "AccountsReceivableNetCurrent", rank, contact_email)
        inventory = _required_instant_at(cik, "InventoryNet", rank, contact_email)
        payables = _required_instant_at(cik, "AccountsPayableCurrent", rank, contact_email)
        return receivables + inventory - payables

    return _to_millions(nwc_at(0) - nwc_at(1))


def _effective_tax_rate(cik: int, contact_email: str) -> float | None:
    pretax_income = _optional(
        cik,
        ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
        _latest_duration,
        contact_email,
    )
    tax_expense = _optional(cik, ["IncomeTaxExpenseBenefit"], _latest_duration, contact_email)

    if pretax_income is None or tax_expense is None or pretax_income <= 0:
        return None

    tax_rate = tax_expense / pretax_income * 100
    if not (0.0 <= tax_rate <= _MAX_PLAUSIBLE_TAX_RATE):
        return None
    return tax_rate


def fetch_fundamentals(cik: int, contact_email: str) -> dict | None:
    """LPA, VPA, ROE and share count for `cik`. Returns `None` if any
    required tag can't be found (e.g. unusual taxonomy) or if
    equity/shares aren't positive."""
    if not contact_email:
        raise SecEdgarError("SEC_EDGAR_CONTACT_EMAIL is not configured")

    try:
        eps = _required(cik, ["EarningsPerShareDiluted"], _latest_duration, contact_email)
        equity = _required(
            cik, ["StockholdersEquity"], lambda rows: _latest_instant(rows, 0), contact_email
        )
        net_income = _required(cik, ["NetIncomeLoss"], _latest_duration, contact_email)
        shares = _required(
            cik,
            ["CommonStockSharesOutstanding"],
            lambda rows: _latest_instant(rows, 0),
            contact_email,
        )
    except LookupError:
        return None

    if equity <= 0 or shares <= 0:
        return None

    return {
        "lpa": eps,
        "vpa": equity / shares,
        "roe": net_income / equity * 100,
        "shares_outstanding": shares,
    }


def fetch_dcf_fundamentals(cik: int, contact_email: str) -> dict | None:
    """The 9 DCF/FCFF accounting fields for `cik`'s most recent fiscal
    year. Returns `None` if EBIT or any other required field can't be
    found (expected for banks, see module docstring)."""
    if not contact_email:
        raise SecEdgarError("SEC_EDGAR_CONTACT_EMAIL is not configured")

    ebit_row = _try_tags(cik, ["OperatingIncomeLoss"], _latest_duration, contact_email)
    if ebit_row is None:
        return None

    try:
        long_term_debt = _required(
            cik, ["LongTermDebtNoncurrent"], lambda rows: _latest_instant(rows, 0), contact_email
        )
        current_debt = _optional(
            cik, ["LongTermDebtCurrent"], lambda rows: _latest_instant(rows, 0), contact_email
        )
        cash = _required(
            cik,
            ["CashAndCashEquivalentsAtCarryingValue"],
            lambda rows: _latest_instant(rows, 0),
            contact_email,
        )
        revenue = _required(
            cik,
            ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
            _latest_duration,
            contact_email,
        )
        inventory = _required(
            cik, ["InventoryNet"], lambda rows: _latest_instant(rows, 0), contact_email
        )
        nwc_change = _nwc_change(cik, contact_email)
    except LookupError:
        return None

    return {
        "reference_year": ebit_row["fy"],
        "ebit": _to_millions(ebit_row["val"]),
        "tax_rate": _effective_tax_rate(cik, contact_email),
        "depreciation_amortization": _to_millions_or_none(
            _optional(
                cik,
                [
                    "DepreciationDepletionAndAmortization",
                    "DepreciationAmortizationAndAccretionNet",
                    "DepreciationAndAmortization",
                    "Depreciation",
                ],
                _latest_duration,
                contact_email,
            )
        ),
        "capex": _to_millions_or_none(
            _optional(
                cik, ["PaymentsToAcquirePropertyPlantAndEquipment"], _latest_duration, contact_email
            )
        ),
        "nwc_change": nwc_change,
        "total_debt": _to_millions(long_term_debt + (current_debt or 0.0)),
        "cash": _to_millions(cash),
        "revenue": _to_millions(revenue),
        "inventory": _to_millions(inventory),
    }


def fetch_payout(cik: int, contact_email: str) -> dict | None:
    """Average payout ratio over the last `PAYOUT_YEARS_AVERAGED` fiscal
    years available (sum of dividends ÷ sum of net income, summed year by
    year before dividing once — same method as `cvm_dfp.fetch_payout`).
    Returns `None` if no year has both net income and dividend data."""
    if not contact_email:
        raise SecEdgarError("SEC_EDGAR_CONTACT_EMAIL is not configured")

    net_income_rows = _fetch_concept(cik, "NetIncomeLoss", contact_email)
    if not net_income_rows:
        return None

    net_income_by_year = {
        r["fy"]: r["val"] for r in sorted(_annual_rows(net_income_rows), key=lambda r: r["filed"])
    }

    # Merges the years from both dividend tags instead of "first tag with
    # any data wins" — a tag can have data only up to an old year and
    # still unfairly "win". Order in DIVIDEND_TAGS (primary first) only
    # decides ties on the same year: iterated in reverse so the primary
    # tag overwrites last.
    dividends_by_year: dict[int, float] = {}
    for tag in reversed(DIVIDEND_TAGS):
        rows = _fetch_concept(cik, tag, contact_email)
        annual = _annual_rows(rows) if rows else []
        for r in sorted(annual, key=lambda r: r["filed"]):
            dividends_by_year[r["fy"]] = r["val"]

    years = sorted(set(net_income_by_year) & set(dividends_by_year), reverse=True)[
        :PAYOUT_YEARS_AVERAGED
    ]
    if not years:
        return None

    total_income = sum(net_income_by_year[y] for y in years if net_income_by_year[y] > 0)
    total_dividends = sum(dividends_by_year[y] for y in years if net_income_by_year[y] > 0)
    if total_income <= 0:
        return None

    return {"payout_avg_5y": total_dividends / total_income * 100}


def fetch_reit_fundamentals(cik: int, contact_email: str) -> dict | None:
    """Fase 1.11.2 — real-estate indicators for `cik`'s most recent fiscal
    year. LPA/VPA/ROE and the DCF fields don't fit real estate the same way
    they fit a regular company (same reasoning CVM's FII data never gets
    those either), so REITs get their own shape.

    **Confirmed live against Realty Income, Simon Property, Prologis and
    AvalonBay**: FFO/AFFO and occupancy rate — the indicators that actually
    define a REIT — aren't XBRL tags in any taxonomy (`us-gaap`/`srt`/
    `invest`); they're non-GAAP, reported only as text/tables in the 10-K.
    What's left automatable: revenue, real estate property value, equity,
    LPA, net income.

    Required (returns `None` if missing): revenue, stockholders_equity,
    eps_diluted — the 3 tags consistent across all 4 REITs tested. Optional:
    real estate property value (net/at cost), net income (`NetIncomeLoss`
    is inconsistent across REITs — Simon Property, an UPREIT, doesn't
    report it, uses `ProfitLoss` instead — handled as a tag fallback).
    """
    if not contact_email:
        raise SecEdgarError("SEC_EDGAR_CONTACT_EMAIL is not configured")

    revenue_row = _try_tags(
        cik,
        ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        _latest_duration,
        contact_email,
    )
    if revenue_row is None:
        return None

    try:
        equity = _required(
            cik, ["StockholdersEquity"], lambda rows: _latest_instant(rows, 0), contact_email
        )
        eps = _required(cik, ["EarningsPerShareDiluted"], _latest_duration, contact_email)
    except LookupError:
        return None

    return {
        "reference_year": revenue_row["fy"],
        "revenue": _to_millions(revenue_row["val"]),
        "real_estate_property_net": _to_millions_or_none(
            _optional(
                cik,
                ["RealEstateInvestmentPropertyNet"],
                lambda rows: _latest_instant(rows, 0),
                contact_email,
            )
        ),
        "real_estate_property_at_cost": _to_millions_or_none(
            _optional(
                cik,
                ["RealEstateInvestmentPropertyAtCost"],
                lambda rows: _latest_instant(rows, 0),
                contact_email,
            )
        ),
        "stockholders_equity": _to_millions(equity),
        "net_income": _to_millions_or_none(
            _optional(cik, ["NetIncomeLoss", "ProfitLoss"], _latest_duration, contact_email)
        ),
        "eps_diluted": eps,
    }
