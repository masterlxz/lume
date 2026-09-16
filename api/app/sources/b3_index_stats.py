"""B3 internal index-statistics API client.

Reimplementation of anchor/data-collector/sources/b3_index_stats.py's
behavior (see project/CONTEXT.md for the full source catalog). Endpoint
confirmed live against the real API by the Anchor project — public, no key,
no auth:
GET https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{base64}
where `{base64}` is the base64 of `{"language": "en-us", "index": "<CODE>",
"year": <YEAR>}`. Returns, per year, a fixed 31-row (`day` 1..31) × 12-column
(`rateValue1`..`rateValue12`, jan..dec) grid; `None`/empty string on a
non-trading day or a day that doesn't exist in that month. Value comes as
`"3,314.09"` (thousands comma, decimal point, due to `language=en-us`).
"""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, timezone

import requests

B3_INDEX_STATS_URL = (
    "https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay"
)
REQUEST_TIMEOUT_SECONDS = 15


class B3IndexStatsError(RuntimeError):
    """Raised when the B3 index stats request or response parsing fails."""


def fetch_index_history(index_code: str, start_year: int, end_year: int | None = None) -> list[dict]:
    """Daily point history for a B3 index (IFIX/SMLL/IDIV) between
    `start_year` and `end_year` (inclusive, defaults to the current year),
    one request per year. Returns `[{"price_date": date, "close_price":
    float}, ...]`. Years before the index's base date return an empty grid
    (harmless, just a wasted request, not an error).
    """
    if end_year is None:
        end_year = datetime.now(timezone.utc).year

    results = []
    for year in range(start_year, end_year + 1):
        params = json.dumps({"language": "en-us", "index": index_code, "year": year})
        b64 = base64.b64encode(params.encode()).decode()
        try:
            response = requests.get(
                f"{B3_INDEX_STATS_URL}/{b64}",
                headers={"User-Agent": "lume-api/1.0"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            rows = response.json().get("results", [])
        except (requests.RequestException, ValueError) as exc:
            raise B3IndexStatsError(
                f"B3 index stats request failed for {index_code} ({year}): {exc}"
            ) from exc

        for row in rows:
            day = row["day"]
            for month in range(1, 13):
                raw = row.get(f"rateValue{month}")
                if not raw:
                    continue
                try:
                    price_date = date(year, month, day)
                except ValueError:
                    continue
                results.append(
                    {"price_date": price_date, "close_price": float(raw.replace(",", ""))}
                )
    return results
