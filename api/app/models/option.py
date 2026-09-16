from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OptionSeries(Base):
    """Registered B3 option series (stock/ETF options only, Fase 1.15) —
    a full market snapshot, refreshed via delete-and-reinsert of the whole
    table (see app/services/options_service.py), same reasoning as
    FiiProperty: a series no longer registered must disappear, not linger
    as stale data."""

    __tablename__ = "option_series"

    series_ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    underlying_symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    option_type: Mapped[str] = mapped_column(String(4), nullable=False)
    strike_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    style: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OptionEodQuote(Base):
    """Latest known end-of-day traded price for an option series ticker —
    one row per series, overwritten on refresh. COTAHIST has no bid/ask or
    intraday data, only a daily close, and Fase 1.15 only needs "last
    known mark" (not a price history), so this mirrors StockQuote's
    single-row shape rather than StockPriceHistory's append-only one."""

    __tablename__ = "option_eod_quotes"

    series_ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
