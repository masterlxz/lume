import io
import zipfile
from datetime import date
from unittest.mock import patch

import pytest
import requests

from app.sources.b3_options_series import B3OptionsSeriesError, fetch_authorized_series


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def _call_row(underlying="PETR        ", series="PETRJ199    ", strike="17.610000000000", exp="20261016", style="Europeu"):
    fields = [
        "02", "PETROBRAS", "70", "OPCOES COMPRA", "0", "", underlying, "PN      N2",
        "00000000", "000000", "0.000000000000", "0.000000000000", "", series,
        "2" if style == "Europeu" else "1", style, strike, exp, "0.000000000000",
    ]
    return "|".join(fields)


def _put_row(underlying="BOVA  FM    ", series="BOVAV125    ", strike="12.500000000000", exp="20261016"):
    fields = [
        "02", "ISHARES BOVA", "80", "OPCOES VENDA", "0", "", underlying, "CI",
        "00000000", "000000", "0.000000000000", "0.000000000000", "", series,
        "2", "Europeu", strike, exp, "0.000000000000",
    ]
    return "|".join(fields)


def _index_points_row():
    # Type "03" (raw index-points options) — out of scope, must be skipped.
    fields = [
        "03", "70", "OPC.COMP.INDICE", "6", "INDICES(PONTOS)", "IBOVESPA    ",
        "51 PONTO = R$   1,00", "40001231", "0.000000000000", "186502.640000000000",
        "20260915", "IBOVJ170W2  ", "2", "Europeu", "170000.000000000000",
        "170000.000000000000", "20261007",
    ]
    return "|".join(fields)


def _build_zip(lines: list[str]) -> bytes:
    header = "01|20260915|20260916|00:01:43"
    text = "\r\n".join([header] + lines) + "\r\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("SI_D_SEDE.txt", text.encode("latin-1"))
    return buffer.getvalue()


def test_fetch_authorized_series_parses_calls_and_puts_only_type_02():
    raw = _build_zip([_call_row(), _put_row(), _index_points_row()])
    with patch("app.sources.b3_options_series.requests.get", return_value=_FakeResponse(raw)):
        result = fetch_authorized_series()

    assert len(result) == 2
    call = next(r for r in result if r["option_type"] == "CALL")
    assert call["series_ticker"] == "PETRJ199"
    assert call["underlying_symbol"] == "PETR"
    assert call["strike_price"] == pytest.approx(17.61)
    assert call["expiration_date"] == date(2026, 10, 16)
    assert call["style"] == "EUROPEAN"

    put = next(r for r in result if r["option_type"] == "PUT")
    assert put["series_ticker"] == "BOVAV125"
    assert put["underlying_symbol"] == "BOVA"


def test_fetch_authorized_series_wraps_network_error():
    with patch(
        "app.sources.b3_options_series.requests.get",
        side_effect=requests.ConnectionError("boom"),
    ):
        with pytest.raises(B3OptionsSeriesError):
            fetch_authorized_series()


def test_fetch_authorized_series_wraps_malformed_zip():
    with patch(
        "app.sources.b3_options_series.requests.get",
        return_value=_FakeResponse(b"not a zip file"),
    ):
        with pytest.raises(B3OptionsSeriesError):
            fetch_authorized_series()
