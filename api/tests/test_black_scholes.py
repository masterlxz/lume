import pytest

from app.services.black_scholes import greeks, implied_volatility, price

# Textbook reference case (Hull): S=100, K=100, T=1, r=5%, sigma=20%.
_S, _K, _T, _R, _SIGMA = 100.0, 100.0, 1.0, 0.05, 0.20


def test_price_matches_textbook_reference_case():
    assert price("CALL", _S, _K, _T, _R, _SIGMA) == pytest.approx(10.4506, abs=1e-3)
    assert price("PUT", _S, _K, _T, _R, _SIGMA) == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity_holds():
    import math

    call = price("CALL", _S, _K, _T, _R, _SIGMA)
    put = price("PUT", _S, _K, _T, _R, _SIGMA)
    assert call - put == pytest.approx(_S - _K * math.exp(-_R * _T), abs=1e-6)


def test_greeks_match_textbook_reference_case():
    call_greeks = greeks("CALL", _S, _K, _T, _R, _SIGMA)
    assert call_greeks["delta"] == pytest.approx(0.6368, abs=1e-3)
    assert call_greeks["gamma"] == pytest.approx(0.018762, abs=1e-4)
    assert call_greeks["vega"] == pytest.approx(0.37524, abs=1e-3)
    assert call_greeks["theta"] == pytest.approx(-0.017573, abs=1e-4)

    put_greeks = greeks("PUT", _S, _K, _T, _R, _SIGMA)
    assert put_greeks["delta"] == pytest.approx(-0.3632, abs=1e-3)
    # Gamma/vega are identical for calls and puts at the same inputs.
    assert put_greeks["gamma"] == pytest.approx(call_greeks["gamma"])
    assert put_greeks["vega"] == pytest.approx(call_greeks["vega"])


def test_implied_volatility_round_trips_a_known_price():
    known_vol = 0.35
    market_price = price("CALL", _S, _K, _T, _R, known_vol)

    solved_vol = implied_volatility("CALL", market_price, _S, _K, _T, _R)

    assert solved_vol == pytest.approx(known_vol, abs=1e-4)


def test_implied_volatility_round_trips_for_puts_too():
    known_vol = 0.5
    market_price = price("PUT", _S, _K, _T, _R, known_vol)

    solved_vol = implied_volatility("PUT", market_price, _S, _K, _T, _R)

    assert solved_vol == pytest.approx(known_vol, abs=1e-4)


def test_implied_volatility_returns_none_below_intrinsic_value():
    # A call struck at 100 with spot at 150 has intrinsic value >= 50 —
    # a "market price" of 10 is inconsistent with any positive volatility.
    assert implied_volatility("CALL", 10.0, 150.0, 100.0, _T, _R) is None
