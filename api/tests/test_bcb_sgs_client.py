from datetime import date, datetime
from unittest.mock import patch

import pytest
import requests

from app.sources.bcb_sgs import BcbSgsError, fetch_daily_series, fetch_monthly_series


def _fake_response(payload):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    return FakeResponse()


def test_fetch_monthly_series_parses_payload():
    payload = [
        {"data": "01/06/2003", "valor": "1.14"},
        {"data": "01/07/2003", "valor": "1.35"},
    ]
    with patch("app.sources.bcb_sgs.requests.get", return_value=_fake_response(payload)):
        result = fetch_monthly_series(4391)

    assert result == [
        {"reference_month": date(2003, 6, 1), "value_pct": 1.14},
        {"reference_month": date(2003, 7, 1), "value_pct": 1.35},
    ]


def test_fetch_monthly_series_wraps_network_error():
    with patch(
        "app.sources.bcb_sgs.requests.get",
        side_effect=requests.ConnectionError("boom"),
    ):
        with pytest.raises(BcbSgsError):
            fetch_monthly_series(4391)


def test_fetch_monthly_series_wraps_malformed_json():
    with patch("app.sources.bcb_sgs.requests.get", return_value=_fake_response([{"bad": "shape"}])):
        with pytest.raises(BcbSgsError):
            fetch_monthly_series(4391)


def test_fetch_daily_series_paginates_in_year_windows_and_preserves_real_day():
    # fetch_daily_series pages through multiple <=9-year windows (BCB SGS
    # rejects an unbounded daily-series query with HTTP 406) — this fake
    # answers each window with only the items that actually fall inside it,
    # same as the real API would, regardless of how many windows today's
    # date produces.
    payload = [
        {"data": "12/09/2026", "valor": "14.00"},
        {"data": "15/09/2026", "valor": "14.00"},
    ]

    def _side_effect(*args, **kwargs):
        params = kwargs["params"]
        window_start = datetime.strptime(params["dataInicial"], "%d/%m/%Y").date()
        window_end = datetime.strptime(params["dataFinal"], "%d/%m/%Y").date()
        items = [
            item
            for item in payload
            if window_start <= datetime.strptime(item["data"], "%d/%m/%Y").date() <= window_end
        ]
        return _fake_response(items)

    with patch("app.sources.bcb_sgs.requests.get", side_effect=_side_effect) as mock_get:
        result = fetch_daily_series(432)

    assert mock_get.call_count > 1  # confirms it actually paginated
    assert result == [
        {"reference_date": date(2026, 9, 12), "value_pct": 14.00},
        {"reference_date": date(2026, 9, 15), "value_pct": 14.00},
    ]


def test_fetch_daily_series_wraps_network_error():
    with patch(
        "app.sources.bcb_sgs.requests.get",
        side_effect=requests.ConnectionError("boom"),
    ):
        with pytest.raises(BcbSgsError):
            fetch_daily_series(432)
