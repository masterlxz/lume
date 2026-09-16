from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.rates import DiFuturesCurveResponse, SelicResponse
from app.services.rates_service import (
    NoCurveDataError,
    UnknownSelicSeriesError,
    get_or_refresh_di_futures_curve,
    get_or_refresh_selic,
)
from app.sources.b3_taxa_swap import B3TaxaSwapError
from app.sources.bcb_sgs import BcbSgsError

router = APIRouter(prefix="/v1/rates", tags=["rates"])


@router.get("/selic/{series_code}", response_model=SelicResponse)
def get_selic_series(
    series_code: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_api_key),
):
    try:
        return get_or_refresh_selic(db, series_code, settings.cache_ttl_seconds)
    except UnknownSelicSeriesError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown Selic series code: {series_code}"
        )
    except BcbSgsError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch data from BCB SGS and no cached data available",
        )


@router.get("/di-futures-curve/{reference_date}", response_model=DiFuturesCurveResponse)
def get_di_futures_curve(
    reference_date: date,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_api_key),
):
    try:
        return get_or_refresh_di_futures_curve(db, reference_date, settings.cache_ttl_seconds)
    except NoCurveDataError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No DI futures curve data for {reference_date.isoformat()}",
        )
    except B3TaxaSwapError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch data from B3 and no cached data available",
        )
