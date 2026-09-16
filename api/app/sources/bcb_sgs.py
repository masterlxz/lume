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

from datetime import date, timedelta

import requests

BCB_SGS_URL_TEMPLATE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
REQUEST_TIMEOUT_SECONDS = 15

# BCB SGS recusa (HTTP 406) uma busca sem `dataInicial` numa série diária —
# "O sistema aceita uma janela de consulta de, no máximo, 10 anos em séries
# de periodicidade diária" (confirmado ao vivo). Séries mensais (CDI/IPCA)
# não têm esse limite. 9 anos de margem de segurança sob o teto real de 10.
DAILY_SERIES_WINDOW_YEARS = 9
# Nenhuma série diária do BCB começa antes disso — janelas anteriores ao
# início real da série só voltam vazias (mesmo raciocínio inofensivo do
# `b3_index_stats.py` pra anos antes da base do índice).
DAILY_SERIES_EARLIEST_YEAR = 1994


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


def fetch_daily_series(series_code: int) -> list[dict]:
    """Fetch the full historical daily series for `series_code`.

    Same response shape as `fetch_monthly_series`, but keeps the real
    day-of-month instead of forcing it to the 1st — for series that
    actually publish one value per business day (e.g. Meta Selic, BCB code
    432), not once a month. Returns `[{"reference_date": date, "value_pct":
    float}, ...]`.

    Unlike `fetch_monthly_series`, this paginates in
    `DAILY_SERIES_WINDOW_YEARS`-year windows via `dataInicial`/`dataFinal` —
    confirmed live that BCB SGS answers HTTP 406 for an unbounded daily
    query ("O sistema aceita uma janela de consulta de, no máximo, 10 anos
    em séries de periodicidade diária"). Windows before the series actually
    starts just come back empty (harmless wasted request, same reasoning as
    `b3_index_stats.fetch_index_history` for years before an index's base
    date).
    """
    results = []
    window_start = date(DAILY_SERIES_EARLIEST_YEAR, 1, 1)
    today = date.today()

    try:
        while window_start <= today:
            window_end = min(
                date(window_start.year + DAILY_SERIES_WINDOW_YEARS, 1, 1) - timedelta(days=1),
                today,
            )
            response = requests.get(
                BCB_SGS_URL_TEMPLATE.format(code=series_code),
                params={
                    "formato": "json",
                    "dataInicial": window_start.strftime("%d/%m/%Y"),
                    "dataFinal": window_end.strftime("%d/%m/%Y"),
                },
                headers={"User-Agent": "lume-api/1.0"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            raw_items = response.json()

            for item in raw_items:
                day, month, year = item["data"].split("/")
                results.append(
                    {
                        "reference_date": date(int(year), int(month), int(day)),
                        "value_pct": float(item["valor"]),
                    }
                )

            window_start = window_end + timedelta(days=1)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise BcbSgsError(f"BCB SGS request failed for series {series_code}: {exc}") from exc

    return results
