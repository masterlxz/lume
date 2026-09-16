"""B3 "Pesquisa por Pregão" TaxaSwap file client — curva DI futuro (PRE).

Sistema legado da B3 (diferente do UP2DATA novo, que passou a exigir sessão/
Cloudflare a partir de dez/2025) — confirmado ao vivo nesta sessão como
público, sem chave, sem autenticação:

GET https://www.b3.com.br/pesquisapregao/download?filelist=TS{YYMMDD}.ex_,

Devolve um zip externo contendo um blob self-extracting (.ex_) que embute um
zip interno com `TaxaSwap.txt` (texto de largura fixa, latin-1). Layout das
linhas (0-based, conforme manual TaxaSwap da B3):
  [21:26]  código da curva      ex: 'PRE  ', 'DIC  '
  [41:46]  dias corridos
  [46:51]  dias úteis
  [51]     sinal da taxa (+ ou -)
  [52:66]  taxa teórica (14 dígitos, 7 decimais → ÷ 1e9 = decimal)
  [66]     característica do vértice (F=fixo / M=móvel)

Curva 'PRE' = DIxPRE = a curva de juros prefixada implícita nos futuros de
DI (o "DI futuro" do roadmap). Uma data sem pregão (fim de semana, feriado)
devolve HTTP 200 com um zip de 22 bytes (vazio) — não é erro, é "sem dado".

TLS validou normalmente nos testes ao vivo desta sessão — ao contrário de
implementações de referência vistas por aí, não desabilitamos a verificação
de certificado aqui.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date

import requests

TAXA_SWAP_URL_TEMPLATE = "https://www.b3.com.br/pesquisapregao/download?filelist=TS{yymmdd}.ex_,"
REQUEST_TIMEOUT_SECONDS = 30
CURVE_CODE = "PRE"
EMPTY_ZIP_MAX_SIZE = 22
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class B3TaxaSwapError(RuntimeError):
    """Raised when the B3 TaxaSwap request or file parsing fails."""


def _extract_taxa_swap_txt(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as outer_zip:
        outer_names = outer_zip.namelist()
        if not outer_names:
            raise B3TaxaSwapError("Outer .ex_ zip is empty")
        inner_blob = outer_zip.read(outer_names[0])

    inner_zip_offset = inner_blob.find(b"PK\x03\x04")
    if inner_zip_offset < 0:
        raise B3TaxaSwapError("Could not locate inner zip signature inside .ex_ blob")

    with zipfile.ZipFile(io.BytesIO(inner_blob[inner_zip_offset:])) as inner_zip:
        inner_names = inner_zip.namelist()
        if not inner_names:
            raise B3TaxaSwapError("Inner zip is empty")
        return inner_zip.read(inner_names[0]).decode("latin-1")


def fetch_pre_curve(reference_date: date) -> list[dict]:
    """Fetch the DIxPRE curve (all vertices) for `reference_date`.

    Returns `[{"dias_corridos": int, "dias_uteis": int, "rate_pct": float,
    "vertice_type": "F"|"M"}, ...]`. Returns an empty list for a date
    without trading (weekend/holiday) — that's a valid response, not an
    error, signaled by B3 via a near-empty zip.
    """
    yymmdd = reference_date.strftime("%y%m%d")
    url = TAXA_SWAP_URL_TEMPLATE.format(yymmdd=yymmdd)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        raw = response.content

        if len(raw) <= EMPTY_ZIP_MAX_SIZE:
            return []

        txt = _extract_taxa_swap_txt(raw)

        results = []
        for line in txt.splitlines():
            line = line.rstrip("\r\n")
            if len(line) < 67 or line[21:26].rstrip() != CURVE_CODE:
                continue

            dias_corridos = int(line[41:46])
            dias_uteis = int(line[46:51])
            sign = 1 if line[51] == "+" else -1
            rate_pct = sign * int(line[52:66]) / 1e9 * 100
            vertice_type = line[66]

            results.append(
                {
                    "dias_corridos": dias_corridos,
                    "dias_uteis": dias_uteis,
                    "rate_pct": rate_pct,
                    "vertice_type": vertice_type,
                }
            )
    except (requests.RequestException, zipfile.BadZipFile, ValueError, IndexError) as exc:
        raise B3TaxaSwapError(
            f"B3 TaxaSwap request/parse failed for {reference_date.isoformat()}: {exc}"
        ) from exc

    return results
