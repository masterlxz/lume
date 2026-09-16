from datetime import date
from unittest.mock import patch

import pytest

from app.services.options_service import get_series_with_last_quote
from app.sources.b3_cotahist import B3CotahistError
from app.sources.b3_options_series import B3OptionsSeriesError

_SERIES = [
    {
        "series_ticker": "PETRJ199",
        "underlying_symbol": "PETR",
        "option_type": "CALL",
        "strike_price": 17.61,
        "expiration_date": date(2026, 10, 16),
        "style": "EUROPEAN",
    },
    {
        "series_ticker": "PETRJ905",
        "underlying_symbol": "PETR",
        "option_type": "CALL",
        "strike_price": 42.25,
        "expiration_date": date(2026, 12, 18),
        "style": "AMERICAN",
    },
]
_QUOTES = {"PETRJ199": {"trade_date": date(2026, 9, 14), "close_price": 31.85}}


def _patched(db, ttl_seconds=3600, series=_SERIES, quotes=_QUOTES):
    with patch("app.services.options_service.fetch_authorized_series", return_value=series):
        with patch("app.services.options_service.fetch_latest_option_quotes", return_value=quotes):
            return get_series_with_last_quote(db, "petr4", ttl_seconds)


def test_first_call_fetches_and_joins_quote(db_session):
    result = _patched(db_session)

    assert result["underlying_symbol"] == "PETR"
    assert result["cached"] is False
    assert result["stale"] is False
    assert len(result["data"]) == 2

    with_quote = next(d for d in result["data"] if d["series_ticker"] == "PETRJ199")
    assert float(with_quote["last_price"]) == pytest.approx(31.85)
    assert with_quote["last_trade_date"] == date(2026, 9, 14)

    without_quote = next(d for d in result["data"] if d["series_ticker"] == "PETRJ905")
    assert without_quote["last_price"] is None
    assert without_quote["last_trade_date"] is None


def test_second_call_within_ttl_uses_cache(db_session):
    _patched(db_session)

    with patch("app.services.options_service.fetch_authorized_series") as mock_series:
        with patch("app.services.options_service.fetch_latest_option_quotes") as mock_quotes:
            result = get_series_with_last_quote(db_session, "petr4", ttl_seconds=3600)

    assert not mock_series.called
    assert not mock_quotes.called
    assert result["cached"] is True
    assert len(result["data"]) == 2


def test_unknown_underlying_returns_empty_data_not_error(db_session):
    result = _patched(db_session)
    with patch("app.services.options_service.fetch_authorized_series", return_value=_SERIES):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes", return_value=_QUOTES
        ):
            result = get_series_with_last_quote(db_session, "xyz9", ttl_seconds=3600)

    assert result["data"] == []


def test_series_source_error_with_cache_serves_stale(db_session):
    _patched(db_session, ttl_seconds=0)

    with patch(
        "app.services.options_service.fetch_authorized_series",
        side_effect=B3OptionsSeriesError("down"),
    ):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes", return_value=_QUOTES
        ):
            result = get_series_with_last_quote(db_session, "petr4", ttl_seconds=0)

    assert result["stale"] is True


def test_quotes_source_error_with_cache_serves_stale(db_session):
    _patched(db_session, ttl_seconds=0)

    with patch("app.services.options_service.fetch_authorized_series", return_value=_SERIES):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes",
            side_effect=B3CotahistError("down"),
        ):
            result = get_series_with_last_quote(db_session, "petr4", ttl_seconds=0)

    assert result["stale"] is True


def test_source_error_without_any_cache_raises(db_session):
    with patch(
        "app.services.options_service.fetch_authorized_series",
        side_effect=B3OptionsSeriesError("down"),
    ):
        try:
            get_series_with_last_quote(db_session, "petr4", ttl_seconds=3600)
            assert False, "expected B3OptionsSeriesError"
        except B3OptionsSeriesError:
            pass
