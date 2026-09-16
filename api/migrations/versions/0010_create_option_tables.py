"""create option tables (option_series, option_eod_quotes)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "option_series",
        sa.Column("series_ticker", sa.String(20), primary_key=True),
        sa.Column("underlying_symbol", sa.String(16), nullable=False),
        sa.Column("option_type", sa.String(4), nullable=False),
        sa.Column("strike_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("expiration_date", sa.Date, nullable=False),
        sa.Column("style", sa.String(10), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_option_series_underlying_symbol", "option_series", ["underlying_symbol"])
    op.create_table(
        "option_eod_quotes",
        sa.Column("series_ticker", sa.String(20), primary_key=True),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("close_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("option_eod_quotes")
    op.drop_index("ix_option_series_underlying_symbol", table_name="option_series")
    op.drop_table("option_series")
