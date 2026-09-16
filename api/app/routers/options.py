from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.options import OptionGreeksResponse, OptionSeriesResponse
from app.services.option_greeks_service import (
    ImpliedVolatilityNotComputableError,
    NoMarketPriceError,
    OptionExpiredError,
    OptionSeriesNotFoundError,
    RiskFreeRateUnavailableError,
    get_option_greeks,
)
from app.services.options_service import get_series_with_last_quote
from app.sources.b3_cotahist import B3CotahistError
from app.sources.b3_options_series import B3OptionsSeriesError
from app.sources.b3_taxa_swap import B3TaxaSwapError
from app.sources.bcb_sgs import BcbSgsError
from app.sources.acoes_yahoo import YahooFinanceError

router = APIRouter(prefix="/v1/options", tags=["options"])

SOURCE_UNAVAILABLE_DETAIL = "Failed to fetch option data from B3 and no cached data available"
GREEKS_SOURCE_UNAVAILABLE_DETAIL = (
    "Failed to fetch one of the underlying data sources (option data, stock quote, or DI "
    "futures curve) and no cached data available"
)

_SOURCE_ERRORS = (
    B3OptionsSeriesError,
    B3CotahistError,
    B3TaxaSwapError,
    BcbSgsError,
    YahooFinanceError,
    RiskFreeRateUnavailableError,
)


@router.get("/{underlying_symbol}/series", response_model=OptionSeriesResponse)
def get_series(
    underlying_symbol: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_api_key),
):
    try:
        return get_series_with_last_quote(db, underlying_symbol, settings.options_ttl_seconds)
    except (B3OptionsSeriesError, B3CotahistError):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=SOURCE_UNAVAILABLE_DETAIL)


@router.get("/{series_ticker}/greeks", response_model=OptionGreeksResponse)
def get_greeks(
    series_ticker: str,
    underlying_ticker: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_api_key),
):
    try:
        return get_option_greeks(db, series_ticker, underlying_ticker, settings)
    except (OptionSeriesNotFoundError, NoMarketPriceError):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No tradable market price available for option series: {series_ticker}",
        )
    except OptionExpiredError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Option series {series_ticker} has already expired",
        )
    except ImpliedVolatilityNotComputableError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Last traded price for {series_ticker} is below intrinsic value — no "
                "volatility reproduces it (likely a stale trade)"
            ),
        )
    except _SOURCE_ERRORS:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=GREEKS_SOURCE_UNAVAILABLE_DETAIL)
