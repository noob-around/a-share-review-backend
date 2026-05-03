"""Add review status.

Revision ID: 0002_add_review_status
Revises: 0001_initial
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_review_status"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "daily_reviews",
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("daily_reviews", "status")
