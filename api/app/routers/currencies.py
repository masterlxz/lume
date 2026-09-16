from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.currency import CurrencyPriceHistoryResponse, CurrencyQuoteResponse
from app.services.currency_service import (
    UnknownCurrencyPairError,
    get_or_refresh_price_history,
    get_or_refresh_quote,
)
from app.sources.acoes_yahoo import YahooFinanceError

router = APIRouter(prefix="/v1/currencies/{pair_code}", tags=["currencies"])

SOURCE_UNAVAILABLE_DETAIL = "Failed to fetch data from Yahoo Finance and no cached data available"


@router.get("/quote", response_model=CurrencyQuoteResponse)
def get_quote(
    pair_code: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_api_key),
):
    try:
        return get_or_refresh_quote(db, pair_code, settings.stock_quote_ttl_seconds)
    except UnknownCurrencyPairError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown currency pair: {pair_code}"
        )
    except YahooFinanceError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=SOURCE_UNAVAILABLE_DETAIL)


@router.get("/price-history", response_model=CurrencyPriceHistoryResponse)
def get_price_history(
    pair_code: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_api_key),
):
    try:
        return get_or_refresh_price_history(db, pair_code, settings.cache_ttl_seconds)
    except UnknownCurrencyPairError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown currency pair: {pair_code}"
        )
    except YahooFinanceError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=SOURCE_UNAVAILABLE_DETAIL)
