from datetime import date
from unittest.mock import patch

import pytest

from app.services.currency_service import (
    UnknownCurrencyPairError,
    get_or_refresh_price_history,
    get_or_refresh_quote,
)
from app.sources.acoes_yahoo import YahooFinanceError


def test_unknown_currency_pair_raises(db_session):
    with pytest.raises(UnknownCurrencyPairError):
        get_or_refresh_quote(db_session, "xyzusd", ttl_seconds=3600)
    with pytest.raises(UnknownCurrencyPairError):
        get_or_refresh_quote(db_session, "usdusd", ttl_seconds=3600)
    with pytest.raises(UnknownCurrencyPairError):
        get_or_refresh_price_history(db_session, "xyzusd", ttl_seconds=3600)


def test_quote_first_call_fetches_and_caches(db_session):
    quote = {"price": 1.1541, "name": None, "exchange": "CCY", "currency": "USD"}
    with patch("app.services.currency_service.fetch_quote", return_value=quote) as mock_fetch:
        result = get_or_refresh_quote(db_session, "eurusd", ttl_seconds=3600)

    assert mock_fetch.called
    mock_fetch.assert_called_with("EURUSD=X", suffix="")
    assert result["cached"] is False
    assert result["base_currency"] == "eur"
    assert result["quote_currency"] == "usd"
    assert float(result["price"]) == 1.1541


def test_quote_second_call_within_ttl_uses_cache(db_session):
    quote = {"price": 1.1541, "name": None, "exchange": "CCY", "currency": "USD"}
    with patch("app.services.currency_service.fetch_quote", return_value=quote) as mock_fetch:
        get_or_refresh_quote(db_session, "eurusd", ttl_seconds=3600)
        result = get_or_refresh_quote(db_session, "eurusd", ttl_seconds=3600)

    assert mock_fetch.call_count == 1
    assert result["cached"] is True


def test_quote_source_error_with_cache_serves_stale(db_session):
    quote = {"price": 1.1541, "name": None, "exchange": "CCY", "currency": "USD"}
    with patch("app.services.currency_service.fetch_quote", return_value=quote):
        get_or_refresh_quote(db_session, "eurusd", ttl_seconds=0)
    with patch(
        "app.services.currency_service.fetch_quote", side_effect=YahooFinanceError("down")
    ):
        result = get_or_refresh_quote(db_session, "eurusd", ttl_seconds=0)

    assert result["stale"] is True


def test_price_history_first_call_fetches_and_caches(db_session):
    points = [{"price_date": date(2026, 1, 2), "close_price": 1.1541}]
    with patch(
        "app.services.currency_service.fetch_price_history", return_value=points
    ) as mock_fetch:
        result = get_or_refresh_price_history(db_session, "eurusd", ttl_seconds=3600)

    mock_fetch.assert_called_with("EURUSD=X", suffix="")
    assert len(result["data"]) == 1
