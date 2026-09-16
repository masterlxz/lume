from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

API_KEY_HEADER = {"X-API-Key": "test-key"}


def _override_get_db(db_session):
    def _get_db():
        yield db_session

    return _get_db


def _with_api_key(db_session, monkeypatch):
    monkeypatch.setenv("API_KEYS", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    return TestClient(app)


def _clear(monkeypatch):
    app.dependency_overrides.clear()
    from app.config import get_settings

    get_settings.cache_clear()


def test_unknown_selic_series_returns_404(db_session, monkeypatch):
    client = _with_api_key(db_session, monkeypatch)
    response = client.get("/v1/rates/selic/nao-existe", headers=API_KEY_HEADER)
    _clear(monkeypatch)

    assert response.status_code == 404


def test_selic_returns_200(db_session, monkeypatch):
    client = _with_api_key(db_session, monkeypatch)

    points = [{"reference_date": date(2026, 9, 15), "value_pct": 14.00}]
    with patch("app.services.rates_service.fetch_daily_series", return_value=points):
        response = client.get("/v1/rates/selic/meta", headers=API_KEY_HEADER)

    _clear(monkeypatch)

    assert response.status_code == 200
    body = response.json()
    assert body["series_code"] == "meta"
    assert body["cached"] is False
    assert body["data"] == [{"reference_date": "2026-09-15", "value_pct": 14.0}]


def test_di_futures_curve_returns_200(db_session, monkeypatch):
    client = _with_api_key(db_session, monkeypatch)

    curve = [
        {"dias_corridos": 1, "dias_uteis": 1, "rate_pct": 13.90, "vertice_type": "F"},
    ]
    with patch("app.services.rates_service.fetch_pre_curve", return_value=curve):
        response = client.get("/v1/rates/di-futures-curve/2026-09-15", headers=API_KEY_HEADER)

    _clear(monkeypatch)

    assert response.status_code == 200
    body = response.json()
    assert body["reference_date"] == "2026-09-15"
    assert body["data"] == [
        {"dias_corridos": 1, "dias_uteis": 1, "rate_pct": 13.9, "vertice_type": "F"}
    ]


def test_di_futures_curve_returns_404_for_non_trading_day(db_session, monkeypatch):
    client = _with_api_key(db_session, monkeypatch)

    with patch("app.services.rates_service.fetch_pre_curve", return_value=[]):
        response = client.get("/v1/rates/di-futures-curve/2026-09-13", headers=API_KEY_HEADER)

    _clear(monkeypatch)

    assert response.status_code == 404
