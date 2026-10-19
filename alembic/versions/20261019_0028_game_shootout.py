"""games: is_shootout — победа в серии буллитов

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-19

Матч, решённый буллитами, по счёту неотличим от победы в основное время, а очков
даёт другое число: проигравший забирает 1 вместо 0. Отличить это можно только
отдельным признаком — из счёта он не выводится.

Колонка NOT NULL с умолчанием false: у всех ранее заведённых матчей буллитов не
было, кроме трёх, их помечают вручную после раскатки.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("is_shootout", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("games", "is_shootout")
