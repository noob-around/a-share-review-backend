"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("market_snapshot", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_date", name="uq_daily_reviews_trade_date"),
    )
    op.create_index(op.f("ix_daily_reviews_id"), "daily_reviews", ["id"], unique=False)

    op.create_table(
        "stock_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=80), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=True),
        sa.Column("buy_reason", sa.Text(), nullable=True),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        sa.Column("sell_reason", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("profit_loss", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("lessons", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_operations_action"), "stock_operations", ["action"], unique=False)
    op.create_index(op.f("ix_stock_operations_id"), "stock_operations", ["id"], unique=False)
    op.create_index(op.f("ix_stock_operations_stock_code"), "stock_operations", ["stock_code"], unique=False)
    op.create_index(op.f("ix_stock_operations_trade_date"), "stock_operations", ["trade_date"], unique=False)
    op.create_index("ix_stock_operations_trade_date_action", "stock_operations", ["trade_date", "action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stock_operations_trade_date_action", table_name="stock_operations")
    op.drop_index(op.f("ix_stock_operations_trade_date"), table_name="stock_operations")
    op.drop_index(op.f("ix_stock_operations_stock_code"), table_name="stock_operations")
    op.drop_index(op.f("ix_stock_operations_id"), table_name="stock_operations")
    op.drop_index(op.f("ix_stock_operations_action"), table_name="stock_operations")
    op.drop_table("stock_operations")
    op.drop_index(op.f("ix_daily_reviews_id"), table_name="daily_reviews")
    op.drop_table("daily_reviews")
