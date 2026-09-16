from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.services import black_scholes
from app.services.option_greeks_service import (
    ImpliedVolatilityNotComputableError,
    NoMarketPriceError,
    OptionExpiredError,
    OptionSeriesNotFoundError,
    RiskFreeRateUnavailableError,
    get_option_greeks,
)
_EXPIRATION = date.today() + timedelta(days=60)
_STRIKE = 45.0
_SPOT = 50.0
_RATE_PCT = 12.5
_KNOWN_VOL = 0.40
_MARKET_PRICE = black_scholes.price(
    "CALL", _SPOT, _STRIKE, 60 / 365, _RATE_PCT / 100, _KNOWN_VOL
)

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


def _get_settings():
    from app.config import Settings

    return Settings(database_url="sqlite:///:memory:")


def _patched_call(db, series_ticker="PETRJ450", underlying_ticker="PETR4"):
    settings = _get_settings()
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
                    return get_option_greeks(db, series_ticker, underlying_ticker, settings)


def test_happy_path_computes_greeks_close_to_known_inputs(db_session):
    result = _patched_call(db_session)

    assert result["series_ticker"] == "PETRJ450"
    assert result["underlying_ticker"] == "PETR4"
    assert result["spot_price"] == _SPOT
    assert result["strike_price"] == _STRIKE
    assert result["risk_free_rate_pct"] == pytest.approx(_RATE_PCT)
    assert result["implied_volatility_pct"] == pytest.approx(_KNOWN_VOL * 100, abs=0.1)
    assert 0 < result["delta"] < 1
    assert result["gamma"] > 0
    assert result["vega"] > 0


def test_unknown_series_raises(db_session):
    with pytest.raises(OptionSeriesNotFoundError):
        _patched_call(db_session, series_ticker="DOESNOTEXIST")


def test_series_without_trade_raises(db_session):
    settings = _get_settings()
    series_only = [
        {
            "series_ticker": "PETRJ999",
            "underlying_symbol": "PETR",
            "option_type": "CALL",
            "strike_price": _STRIKE,
            "expiration_date": _EXPIRATION,
            "style": "EUROPEAN",
        }
    ]
    with patch("app.services.options_service.fetch_authorized_series", return_value=series_only):
        with patch("app.services.options_service.fetch_latest_option_quotes", return_value={}):
            with pytest.raises(NoMarketPriceError):
                get_option_greeks(db_session, "PETRJ999", "PETR4", settings)


def test_expired_option_raises(db_session):
    settings = _get_settings()
    expired_series = [
        {
            "series_ticker": "PETRJ001",
            "underlying_symbol": "PETR",
            "option_type": "CALL",
            "strike_price": _STRIKE,
            "expiration_date": date.today() - timedelta(days=1),
            "style": "EUROPEAN",
        }
    ]
    expired_quotes = {"PETRJ001": {"trade_date": date.today(), "close_price": 5.0}}
    with patch(
        "app.services.options_service.fetch_authorized_series", return_value=expired_series
    ):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes",
            return_value=expired_quotes,
        ):
            with pytest.raises(OptionExpiredError):
                get_option_greeks(db_session, "PETRJ001", "PETR4", settings)


def test_price_below_intrinsic_raises_not_computable(db_session):
    settings = _get_settings()
    deep_itm_series = [
        {
            "series_ticker": "PETRJ010",
            "underlying_symbol": "PETR",
            "option_type": "CALL",
            "strike_price": 10.0,
            "expiration_date": _EXPIRATION,
            "style": "EUROPEAN",
        }
    ]
    # Spot far above strike (intrinsic ~40), but "market price" of 1.0 — impossible.
    stale_quotes = {"PETRJ010": {"trade_date": date.today(), "close_price": 1.0}}
    with patch(
        "app.services.options_service.fetch_authorized_series", return_value=deep_itm_series
    ):
        with patch(
            "app.services.options_service.fetch_latest_option_quotes", return_value=stale_quotes
        ):
            with patch(
                "app.services.option_greeks_service.get_or_refresh_quote",
                return_value={"price": _SPOT},
            ):
                with patch(
                    "app.services.option_greeks_service.get_or_refresh_di_futures_curve",
                    return_value={"data": _VERTICES},
                ):
                    with pytest.raises(ImpliedVolatilityNotComputableError):
                        get_option_greeks(db_session, "PETRJ010", "PETR4", settings)


def test_di_curve_falls_back_across_weekend(db_session):
    settings = _get_settings()
    call_count = {"n": 0}

    from app.services.rates_service import NoCurveDataError

    def _fake_curve_with_no_data(db, reference_date, ttl_seconds):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise NoCurveDataError(reference_date)
        return {"data": _VERTICES}

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
                    side_effect=_fake_curve_with_no_data,
                ):
                    result = get_option_greeks(db_session, "PETRJ450", "PETR4", settings)

    assert call_count["n"] == 3
    assert result["implied_volatility_pct"] == pytest.approx(_KNOWN_VOL * 100, abs=0.1)


def test_di_curve_unavailable_raises(db_session):
    settings = _get_settings()
    from app.services.rates_service import NoCurveDataError

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
                    with pytest.raises(RiskFreeRateUnavailableError):
                        get_option_greeks(db_session, "PETRJ450", "PETR4", settings)
