"""create currency tables (currency_quotes, currency_price_history)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "currency_quotes",
        sa.Column("pair_code", sa.String(8), primary_key=True),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "currency_price_history",
        sa.Column("pair_code", sa.String(8), primary_key=True),
        sa.Column("price_date", sa.Date, primary_key=True),
        sa.Column("close_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("currency_price_history")
    op.drop_table("currency_quotes")
