from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.options import OptionSeriesResponse
from app.services.options_service import get_series_with_last_quote
from app.sources.b3_cotahist import B3CotahistError
from app.sources.b3_options_series import B3OptionsSeriesError

router = APIRouter(prefix="/v1/options/{underlying_symbol}", tags=["options"])

SOURCE_UNAVAILABLE_DETAIL = "Failed to fetch option data from B3 and no cached data available"


@router.get("/series", response_model=OptionSeriesResponse)
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
