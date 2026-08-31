"""game_player_stats: minutes_played — минуты вратаря в матче вручную

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-31

Когда у команды в матче два вратаря, командные броски и голы из табло между ними
распределить нельзя — ПШ/ОБ остаются неизвестными. Но время на льду известно,
и его можно записать. Колонка nullable: пусто — минуты считаются по регламенту
для единственного вратаря команды, как раньше.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_player_stats", sa.Column("minutes_played", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("game_player_stats", "minutes_played")
