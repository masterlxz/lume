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


def test_quote_requires_api_key(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    client = TestClient(app)
    response = client.get("/v1/currencies/eurusd/quote")
    _teardown()

    assert response.status_code == 401


def test_quote_returns_200(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    quote = {"price": 1.1541, "name": None, "exchange": "CCY", "currency": "USD"}
    with patch("app.services.currency_service.fetch_quote", return_value=quote):
        response = client.get("/v1/currencies/eurusd/quote", headers=API_KEY_HEADER)
    _teardown()

    assert response.status_code == 200
    assert response.json()["price"] == 1.1541


def test_quote_returns_404_for_unknown_pair(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    response = client.get("/v1/currencies/usdusd/quote", headers=API_KEY_HEADER)
    _teardown()

    assert response.status_code == 404


def test_price_history_returns_200(db_session, monkeypatch):
    client = _client_with_auth(db_session, monkeypatch)
    points = [{"price_date": date(2026, 1, 2), "close_price": 1.1541}]
    with patch("app.services.currency_service.fetch_price_history", return_value=points):
        response = client.get("/v1/currencies/eurusd/price-history", headers=API_KEY_HEADER)
    _teardown()

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
