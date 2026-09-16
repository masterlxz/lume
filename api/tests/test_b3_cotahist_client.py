import zipfile
from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest
import requests

from app.sources.b3_cotahist import B3CotahistError, fetch_latest_option_quotes


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def _cotahist_line(codneg: str, tpmerc: str, data: str, preult_reais: float, totneg: int = 1) -> str:
    """Builds one 245-byte fixed-width COTAHIST row with only the fields
    `b3_cotahist.py` actually reads set meaningfully; everything else is
    zero-filled filler matching the real column widths."""
    preult = str(round(preult_reais * 100)).rjust(13, "0")
    return (
        "01"  # TIPREG [0:2]
        + data  # DATA [2:10]
        + "78"  # CODBDI [10:12]
        + codneg.ljust(12)  # CODNEG [12:24]
        + tpmerc  # TPMERC [24:27]
        + "X" * 12  # NOMRES [27:39]
        + "X" * 10  # ESPECI [39:49]
        + "0" * 3  # PRAZOT [49:52]
        + "R$  "  # MODREF [52:56]
        + "0" * 13  # PREABE [56:69]
        + "0" * 13  # PREMAX [69:82]
        + "0" * 13  # PREMIN [82:95]
        + "0" * 13  # PREMED [95:108]
        + preult  # PREULT [108:121]
        + "0" * 13  # PREOFC [121:134]
        + "0" * 13  # PREOFV [134:147]
        + str(totneg).rjust(5, "0")  # TOTNEG [147:152]
        + "0" * 18  # QUATOT [152:170]
        + "0" * 18  # VOLTOT [170:188]
        + "0" * 13  # PREEXE [188:201]
        + "0"  # INDOPC [201:202]
        + "20261016"  # DATVEN [202:210]
        + "0" * 7  # FATCOT [210:217]
        + "0" * 13  # PTOEXE [217:230]
        + "X" * 12  # CODISI [230:242]
        + "0" * 3  # DISMES [242:245]
    )


def _build_zip(lines: list[str]) -> bytes:
    text = "\r\n".join(lines) + "\r\n"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("COTAHIST_A2026.TXT", text.encode("latin-1"))
    return buffer.getvalue()


def test_fetch_latest_option_quotes_keeps_only_most_recent_price_per_series():
    raw = _build_zip(
        [
            _cotahist_line("PETRJ199", "070", "20260819", 25.02),
            _cotahist_line("PETRJ199", "070", "20260914", 31.85),  # later date, same series
            _cotahist_line("VALE3", "010", "20260914", 60.00),  # not an option, must be skipped
            _cotahist_line("BOVAV125", "080", "20260910", 12.34),
        ]
    )
    with patch("app.sources.b3_cotahist.requests.get", return_value=_FakeResponse(raw)):
        result = fetch_latest_option_quotes(2026)

    assert set(result.keys()) == {"PETRJ199", "BOVAV125"}
    assert result["PETRJ199"]["close_price"] == pytest.approx(31.85)
    assert result["PETRJ199"]["trade_date"] == date(2026, 9, 14)
    assert result["BOVAV125"]["close_price"] == pytest.approx(12.34)


def test_fetch_latest_option_quotes_wraps_network_error():
    with patch(
        "app.sources.b3_cotahist.requests.get", side_effect=requests.ConnectionError("boom")
    ):
        with pytest.raises(B3CotahistError):
            fetch_latest_option_quotes(2026)


def test_fetch_latest_option_quotes_wraps_malformed_zip():
    with patch(
        "app.sources.b3_cotahist.requests.get", return_value=_FakeResponse(b"not a zip file")
    ):
        with pytest.raises(B3CotahistError):
            fetch_latest_option_quotes(2026)
