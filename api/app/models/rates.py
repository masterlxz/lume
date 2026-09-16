from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SelicDaily(Base):
    """Fase 1.13 — Meta Selic definida pelo Copom (BCB SGS 432), publicada
    diariamente (% a.a.). Mesmo shape de UsStockPriceHistory (append-only,
    uma linha por (series_code, reference_date)) — diferente de
    MacroSeriesMonthly, que é explicitamente mensal (CDI/IPCA)."""

    __tablename__ = "selic_daily"

    series_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    reference_date: Mapped[date] = mapped_column(Date, primary_key=True)
    value_pct: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiFuturesCurveVertex(Base):
    """Fase 1.13 — curva DI futuro (DIxPRE) via arquivo TaxaSwap da B3.
    Cada dia de pregão tem N vértices (um por prazo) — a "lista" aqui é por
    vértice dentro de uma data, não por data dentro de um identificador,
    então `reference_date` faz o papel de id_column e `dias_uteis` o de
    date_column no `get_or_refresh_list` genérico (ver
    app/services/rates_service.py)."""

    __tablename__ = "di_futures_curve"

    reference_date: Mapped[date] = mapped_column(Date, primary_key=True)
    dias_uteis: Mapped[int] = mapped_column(Integer, primary_key=True)
    dias_corridos: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_pct: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    vertice_type: Mapped[str] = mapped_column(String(1), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
