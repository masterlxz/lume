"""Black-Scholes option pricing (Fase 1.16) — pure math, no I/O.

Stdlib `math` only (`erf`/`exp`/`log`/`sqrt`) — no numpy/scipy. This
project has no numerical-computing dependency today (`requirements.txt`),
and a single-formula pricing model doesn't warrant introducing one.

European-style pricing is used for every series, even ones flagged
`AMERICAN` in `option_series.style` (Fase 1.15) — no free source gives an
early-exercise premium to validate against, so approximating American as
European is a deliberate, documented simplification (not a silent error):
in practice this mostly affects deep ITM puts, and BR retail options are
rarely exercised early anyway.

Formulas verified against the standard textbook reference case (Hull):
S=100, K=100, T=1, r=5%, σ=20% → call≈10.4506, put≈5.5735,
delta_call≈0.6368, gamma≈0.018762, vega≈0.3752 (per 1 vol point),
theta_call≈-0.017573/day — see `tests/test_black_scholes.py`.
"""
from __future__ import annotations

import math

_MIN_VOLATILITY = 1e-4
_MAX_VOLATILITY = 5.0
_MAX_NEWTON_ITERATIONS = 50
_MAX_BISECTION_ITERATIONS = 100
_PRICE_TOLERANCE = 1e-6
_INITIAL_VOLATILITY_GUESS = 0.3


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def _d1_d2(spot: float, strike: float, years: float, rate: float, vol: float) -> tuple[float, float]:
    d1 = (math.log(spot / strike) + (rate + vol * vol / 2) * years) / (vol * math.sqrt(years))
    d2 = d1 - vol * math.sqrt(years)
    return d1, d2


def price(option_type: str, spot: float, strike: float, years: float, rate: float, vol: float) -> float:
    d1, d2 = _d1_d2(spot, strike, years, rate, vol)
    if option_type == "CALL":
        return spot * _norm_cdf(d1) - strike * math.exp(-rate * years) * _norm_cdf(d2)
    return strike * math.exp(-rate * years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def greeks(option_type: str, spot: float, strike: float, years: float, rate: float, vol: float) -> dict:
    """`delta`/`gamma` in the usual per-$1-of-spot units, `vega` per 1
    percentage point of volatility, `theta` per calendar day (÷365) —
    market-convention scaling, not raw per-year/per-unit-vol values."""
    d1, d2 = _d1_d2(spot, strike, years, rate, vol)
    pdf_d1 = _norm_pdf(d1)
    discounted_strike = strike * math.exp(-rate * years)

    gamma = pdf_d1 / (spot * vol * math.sqrt(years))
    vega = spot * pdf_d1 * math.sqrt(years) / 100

    if option_type == "CALL":
        delta = _norm_cdf(d1)
        theta = (-spot * pdf_d1 * vol / (2 * math.sqrt(years)) - rate * discounted_strike * _norm_cdf(d2)) / 365
    else:
        delta = _norm_cdf(d1) - 1
        theta = (-spot * pdf_d1 * vol / (2 * math.sqrt(years)) + rate * discounted_strike * _norm_cdf(-d2)) / 365

    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


def implied_volatility(
    option_type: str, market_price: float, spot: float, strike: float, years: float, rate: float
) -> float | None:
    """Solves for the volatility that reproduces `market_price` under
    Black-Scholes (Newton-Raphson using vega as the derivative, falling
    back to bisection if it doesn't converge). Returns `None` if
    `market_price` is below the option's intrinsic value — no positive
    volatility reproduces that, a sign the price is stale/unreliable
    rather than a solver bug.
    """
    intrinsic = max(0.0, (spot - strike) if option_type == "CALL" else (strike - spot))
    if market_price < intrinsic - _PRICE_TOLERANCE:
        return None

    vol = _INITIAL_VOLATILITY_GUESS
    for _ in range(_MAX_NEWTON_ITERATIONS):
        diff = price(option_type, spot, strike, years, rate, vol) - market_price
        if abs(diff) < _PRICE_TOLERANCE:
            return vol
        vega_raw = spot * _norm_pdf(_d1_d2(spot, strike, years, rate, vol)[0]) * math.sqrt(years)
        if vega_raw < 1e-8:
            break
        vol = max(_MIN_VOLATILITY, min(_MAX_VOLATILITY, vol - diff / vega_raw))

    low, high = _MIN_VOLATILITY, _MAX_VOLATILITY
    diff_low = price(option_type, spot, strike, years, rate, low) - market_price
    diff_high = price(option_type, spot, strike, years, rate, high) - market_price
    if diff_low * diff_high > 0:
        return None

    for _ in range(_MAX_BISECTION_ITERATIONS):
        mid = (low + high) / 2
        diff_mid = price(option_type, spot, strike, years, rate, mid) - market_price
        if abs(diff_mid) < _PRICE_TOLERANCE:
            return mid
        if diff_low * diff_mid < 0:
            high = mid
        else:
            low, diff_low = mid, diff_mid
    return (low + high) / 2
