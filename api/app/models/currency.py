from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CurrencyQuote(Base):
    """Latest known quote for a currency pair (by 6-letter pair code, e.g.
    "eurusd") — one row per pair, overwritten on refresh."""

    __tablename__ = "currency_quotes"

    pair_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CurrencyPriceHistory(Base):
    """One closing price per (pair code, trading day) — append-only, a
    past trading day never changes once recorded."""

    __tablename__ = "currency_price_history"

    pair_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    price_date: Mapped[date] = mapped_column(Date, primary_key=True)
    close_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
