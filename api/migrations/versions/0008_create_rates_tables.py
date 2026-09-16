"""create rates tables (selic_daily, di_futures_curve)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "selic_daily",
        sa.Column("series_code", sa.String(32), primary_key=True),
        sa.Column("reference_date", sa.Date, primary_key=True),
        sa.Column("value_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "di_futures_curve",
        sa.Column("reference_date", sa.Date, primary_key=True),
        sa.Column("dias_uteis", sa.Integer, primary_key=True),
        sa.Column("dias_corridos", sa.Integer, nullable=False),
        sa.Column("rate_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("vertice_type", sa.String(1), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("di_futures_curve")
    op.drop_table("selic_daily")
