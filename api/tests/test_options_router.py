from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.main import app

API_KEY_HEADER = {"X-API-Key": "test-key"}


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


def test_series_requires_api_key(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)
    response = client.get("/v1/options/PETR4/series")
    _teardown()

    assert response.status_code == 401


def test_series_returns_200_with_joined_quote(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    series = [
        {
            "series_ticker": "PETRJ199",
            "underlying_symbol": "PETR",
            "option_type": "CALL",
            "strike_price": 17.61,
            "expiration_date": date(2026, 10, 16),
            "style": "EUROPEAN",
        }
    ]
    quotes = {"PETRJ199": {"trade_date": date(2026, 9, 14), "close_price": 31.85}}
    with patch("app.services.options_service.fetch_authorized_series", return_value=series):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes", return_value=quotes
        ):
            response = client.get("/v1/options/PETR4/series", headers=API_KEY_HEADER)
    _teardown()

    assert response.status_code == 200
    body = response.json()
    assert body["underlying_symbol"] == "PETR"
    assert body["data"][0]["last_price"] == 31.85


def test_series_returns_200_with_empty_data_for_unknown_underlying(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    with patch("app.services.options_service.fetch_authorized_series", return_value=[]):
        with patch("app.services.options_service.fetch_latest_option_quotes", return_value={}):
            response = client.get("/v1/options/ZZZZ9/series", headers=API_KEY_HEADER)
    _teardown()

    assert response.status_code == 200
    assert response.json()["data"] == []
