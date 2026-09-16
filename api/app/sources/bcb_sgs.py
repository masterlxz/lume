"""BCB SGS (Sistema Gerenciador de Séries Temporais) HTTP client.

Reimplementation of anchor/data-collector/sources/bcb_sgs.py's behavior (see
project/CONTEXT.md for the full source catalog this project is centralizing).
Endpoint confirmed live against the real BCB API by the Anchor project:
public, no key, no registration required.

GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json
returns `[{"data": "dd/mm/yyyy", "valor": "0.47"}, ...]`. Monthly series
(CDI accumulated = 4391, IPCA monthly change = 433) always report `data` as
the 1st of the month, and `valor` is already the ready-to-use monthly
percentage.
"""
from __future__ import annotations

from datetime import date

import requests

BCB_SGS_URL_TEMPLATE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
REQUEST_TIMEOUT_SECONDS = 15


class BcbSgsError(RuntimeError):
    """Raised when the BCB SGS request or response parsing fails."""


def fetch_monthly_series(series_code: int) -> list[dict]:
    """Fetch the full historical monthly series for `series_code`.

    Fetches the entire series (not `ultimos/N`) since a caller may need to
    backfill any historical range, not just recent months. Returns
    `[{"reference_month": date(YYYY, MM, 1), "value_pct": float}, ...]`.
    """
    try:
        response = requests.get(
            BCB_SGS_URL_TEMPLATE.format(code=series_code),
            params={"formato": "json"},
            headers={"User-Agent": "lume-api/1.0"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        raw_items = response.json()

        results = []
        for item in raw_items:
            day, month, year = item["data"].split("/")
            results.append(
                {
                    "reference_month": date(int(year), int(month), 1),
                    "value_pct": float(item["valor"]),
                }
            )
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise BcbSgsError(f"BCB SGS request failed for series {series_code}: {exc}") from exc

    return results
