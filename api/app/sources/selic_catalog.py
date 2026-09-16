"""Known Selic series catalog.

Deliberately small (Fase 1.13 do project/PHASE.md): só a Meta Selic definida
pelo Copom (código BCB 432, confirmado ao vivo contra a API real nesta
sessão). Separado de `catalog.py` (que é explicitamente mensal, CDI/IPCA) —
esta série é diária. Reaproveita o dataclass `MacroSeriesInfo` já existente
em vez de duplicar o shape.
"""
from app.sources.catalog import MacroSeriesInfo

SELIC_SERIES_CATALOG: dict[str, MacroSeriesInfo] = {
    "meta": MacroSeriesInfo("meta", 432, "Meta Selic (Copom, % a.a.)"),
}


def get_selic_series_info(series_code: str) -> MacroSeriesInfo | None:
    return SELIC_SERIES_CATALOG.get(series_code)
