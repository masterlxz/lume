from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.services import black_scholes
from app.services.rates_service import NoCurveDataError

API_KEY_HEADER = {"X-API-Key": "test-key"}

_EXPIRATION = date.today() + timedelta(days=60)
_STRIKE = 45.0
_SPOT = 50.0
_RATE_PCT = 12.5
_MARKET_PRICE = black_scholes.price("CALL", _SPOT, _STRIKE, 60 / 365, _RATE_PCT / 100, 0.40)

_SERIES = [
    {
        "series_ticker": "PETRJ450",
        "underlying_symbol": "PETR",
        "option_type": "CALL",
        "strike_price": _STRIKE,
        "expiration_date": _EXPIRATION,
        "style": "EUROPEAN",
    }
]
_QUOTES = {"PETRJ450": {"trade_date": date.today(), "close_price": _MARKET_PRICE}}


class _FakeVertex:
    def __init__(self, dias_corridos, rate_pct):
        self.dias_corridos = dias_corridos
        self.rate_pct = rate_pct


_VERTICES = [_FakeVertex(30, 12.5), _FakeVertex(90, 12.5)]


def _override_get_db(db_session):
    def _get_db():
        yield db_session

    return _get_db


def _client_with_auth(db_session, monkeypatch):
    monkeypatch.setenv("API_KEYS", "test-key")
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    return TestClient(app)


def _teardown():
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _mocked_get(client, series_ticker="PETRJ450", underlying_ticker="PETR4"):
    with patch("app.services.options_service.fetch_authorized_series", return_value=_SERIES):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes", return_value=_QUOTES
        ):
            with patch(
                "app.services.option_greeks_service.get_or_refresh_quote",
                return_value={"price": _SPOT},
            ):
                with patch(
                    "app.services.option_greeks_service.get_or_refresh_di_futures_curve",
                    return_value={"data": _VERTICES},
                ):
                    return client.get(
                        f"/v1/options/{series_ticker}/greeks",
                        params={"underlying_ticker": underlying_ticker},
                        headers=API_KEY_HEADER,
                    )


def test_greeks_requires_api_key(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)
    response = client.get("/v1/options/PETRJ450/greeks", params={"underlying_ticker": "PETR4"})
    _teardown()

    assert response.status_code == 401


def test_greeks_returns_200_with_computed_values(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    response = _mocked_get(client)
    _teardown()

    assert response.status_code == 200
    body = response.json()
    assert body["series_ticker"] == "PETRJ450"
    assert body["underlying_ticker"] == "PETR4"
    assert 0 < body["delta"] < 1
    assert body["implied_volatility_pct"] == pytest.approx(40.0, abs=0.5)


def test_greeks_returns_404_for_unknown_series(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    response = _mocked_get(client, series_ticker="DOESNOTEXIST")
    _teardown()

    assert response.status_code == 404


def test_greeks_returns_502_when_di_curve_unavailable(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    with patch("app.services.options_service.fetch_authorized_series", return_value=_SERIES):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes", return_value=_QUOTES
        ):
            with patch(
                "app.services.option_greeks_service.get_or_refresh_quote",
                return_value={"price": _SPOT},
            ):
                with patch(
                    "app.services.option_greeks_service.get_or_refresh_di_futures_curve",
                    side_effect=NoCurveDataError(date.today()),
                ):
                    response = client.get(
                        "/v1/options/PETRJ450/greeks",
                        params={"underlying_ticker": "PETR4"},
                        headers=API_KEY_HEADER,
                    )
    _teardown()

    assert response.status_code == 502
