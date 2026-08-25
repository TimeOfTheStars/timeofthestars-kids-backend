"""teams: city

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-23

Аддитивно: одна nullable-колонка, без backfill. Тип и длина — как у arenas.city,
чтобы город в проекте хранился одинаково.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("city", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "city")
