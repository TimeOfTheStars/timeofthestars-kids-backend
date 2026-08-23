"""tournaments: game_format, period_minutes, periods_count (регламент из шапки протокола)

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-23

Все три колонки nullable без backfill — существующие турниры остаются как есть,
новые поля приходят на фронт как null.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tournaments", sa.Column("game_format", sa.String(length=16), nullable=True))
    op.add_column("tournaments", sa.Column("period_minutes", sa.Integer(), nullable=True))
    op.add_column("tournaments", sa.Column("periods_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tournaments", "periods_count")
    op.drop_column("tournaments", "period_minutes")
    op.drop_column("tournaments", "game_format")
