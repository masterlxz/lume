from datetime import date
from unittest.mock import patch

import pytest

from app.services.rates_service import (
    NoCurveDataError,
    UnknownSelicSeriesError,
    get_or_refresh_di_futures_curve,
    get_or_refresh_selic,
)


# --- Selic (Meta Copom, BCB 432) --------------------------------------------


def test_selic_first_call_fetches_and_caches(db_session):
    payload = [{"reference_date": date(2026, 9, 15), "value_pct": 14.00}]
    with patch(
        "app.services.rates_service.fetch_daily_series", return_value=payload
    ) as mock_fetch:
        result = get_or_refresh_selic(db_session, "meta", ttl_seconds=3600)

    assert mock_fetch.called
    assert result["cached"] is False
    assert len(result["data"]) == 1
    assert float(result["data"][0].value_pct) == 14.00


def test_selic_second_call_within_ttl_serves_cache(db_session):
    payload = [{"reference_date": date(2026, 9, 15), "value_pct": 14.00}]
    with patch("app.services.rates_service.fetch_daily_series", return_value=payload):
        get_or_refresh_selic(db_session, "meta", ttl_seconds=3600)

    with patch(
        "app.services.rates_service.fetch_daily_series",
    ) as mock_fetch:
        result = get_or_refresh_selic(db_session, "meta", ttl_seconds=3600)

    assert not mock_fetch.called
    assert result["cached"] is True


def test_selic_unknown_series_code_raises(db_session):
    with pytest.raises(UnknownSelicSeriesError):
        get_or_refresh_selic(db_session, "nao-existe", ttl_seconds=3600)


# --- DI futuro / curva PRE (B3 TaxaSwap) ------------------------------------


def _curve_point(dias_corridos, dias_uteis, rate_pct=13.90, vertice_type="F"):
    return {
        "dias_corridos": dias_corridos,
        "dias_uteis": dias_uteis,
        "rate_pct": rate_pct,
        "vertice_type": vertice_type,
    }


def test_di_futures_curve_first_call_fetches_and_caches(db_session):
    curve = [_curve_point(1, 1), _curve_point(30, 21, rate_pct=13.70)]
    with patch(
        "app.services.rates_service.fetch_pre_curve", return_value=curve
    ) as mock_fetch:
        result = get_or_refresh_di_futures_curve(db_session, date(2026, 9, 15), ttl_seconds=3600)

    assert mock_fetch.called
    assert result["cached"] is False
    assert len(result["data"]) == 2
    assert float(result["data"][0].rate_pct) == 13.90


def test_di_futures_curve_second_call_within_ttl_serves_cache(db_session):
    curve = [_curve_point(1, 1)]
    with patch("app.services.rates_service.fetch_pre_curve", return_value=curve):
        get_or_refresh_di_futures_curve(db_session, date(2026, 9, 15), ttl_seconds=3600)

    with patch("app.services.rates_service.fetch_pre_curve") as mock_fetch:
        result = get_or_refresh_di_futures_curve(db_session, date(2026, 9, 15), ttl_seconds=3600)

    assert not mock_fetch.called
    assert result["cached"] is True


def test_di_futures_curve_empty_result_raises_no_curve_data(db_session):
    with patch("app.services.rates_service.fetch_pre_curve", return_value=[]):
        with pytest.raises(NoCurveDataError):
            get_or_refresh_di_futures_curve(db_session, date(2026, 9, 13), ttl_seconds=3600)
