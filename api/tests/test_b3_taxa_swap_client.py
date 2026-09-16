import io
import zipfile
from datetime import date
from unittest.mock import patch

import pytest
import requests

from app.sources.b3_taxa_swap import B3TaxaSwapError, fetch_pre_curve


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def _taxa_swap_line(curva: str, dias_corridos: int, dias_uteis: int, rate_decimal: float, vertice: str = "F") -> str:
    seq = "0" * 21
    cod = curva.ljust(5)[:5]
    desc = "X" * 15
    dc_str = str(dias_corridos).rjust(5)
    du_str = str(dias_uteis).rjust(5)
    sign = "+" if rate_decimal >= 0 else "-"
    raw14 = str(round(abs(rate_decimal) * 1e9)).rjust(14, "0")
    tail = "00000"
    return seq + cod + desc + dc_str + du_str + sign + raw14 + vertice + tail


def _build_taxa_swap_zip(lines: list[str]) -> bytes:
    txt = "\r\n".join(lines).encode("latin-1")
    inner_zip_buf = io.BytesIO()
    with zipfile.ZipFile(inner_zip_buf, "w") as inner_zip:
        inner_zip.writestr("TaxaSwap.txt", txt)
    inner_blob = b"SELF_EXTRACTING_EXE_HEADER" + inner_zip_buf.getvalue()

    outer_zip_buf = io.BytesIO()
    with zipfile.ZipFile(outer_zip_buf, "w") as outer_zip:
        outer_zip.writestr("TS260915.ex_", inner_blob)
    return outer_zip_buf.getvalue()


def test_fetch_pre_curve_parses_and_filters_by_curve_code():
    raw = _build_taxa_swap_zip(
        [
            _taxa_swap_line("PRE", 1, 1, 0.1390),
            _taxa_swap_line("DIC", 1, 1, 0.0500),  # different curve, must be ignored
            _taxa_swap_line("PRE", 30, 21, 0.1370, vertice="M"),
        ]
    )
    with patch("app.sources.b3_taxa_swap.requests.get", return_value=_FakeResponse(raw)):
        result = fetch_pre_curve(date(2026, 9, 15))

    assert len(result) == 2
    assert result[0]["dias_corridos"] == 1
    assert result[0]["dias_uteis"] == 1
    assert result[0]["rate_pct"] == pytest.approx(13.90)
    assert result[0]["vertice_type"] == "F"
    assert result[1]["dias_corridos"] == 30
    assert result[1]["dias_uteis"] == 21
    assert result[1]["rate_pct"] == pytest.approx(13.70)
    assert result[1]["vertice_type"] == "M"


def test_fetch_pre_curve_returns_empty_list_for_non_trading_day():
    # B3 answers a weekend/holiday with a near-empty zip (~22 bytes) — not an error.
    empty_zip = io.BytesIO()
    with zipfile.ZipFile(empty_zip, "w"):
        pass

    with patch(
        "app.sources.b3_taxa_swap.requests.get",
        return_value=_FakeResponse(empty_zip.getvalue()),
    ):
        result = fetch_pre_curve(date(2026, 9, 13))

    assert result == []


def test_fetch_pre_curve_wraps_network_error():
    with patch(
        "app.sources.b3_taxa_swap.requests.get",
        side_effect=requests.ConnectionError("boom"),
    ):
        with pytest.raises(B3TaxaSwapError):
            fetch_pre_curve(date(2026, 9, 15))


def test_fetch_pre_curve_wraps_malformed_zip():
    with patch(
        "app.sources.b3_taxa_swap.requests.get",
        return_value=_FakeResponse(b"not a real zip file, but long enough to skip the 22-byte guard"),
    ):
        with pytest.raises(B3TaxaSwapError):
            fetch_pre_curve(date(2026, 9, 15))
