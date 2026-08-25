"""teams: ручные переопределения общей статистики

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-23

Семь nullable-колонок. NULL означает «считать показатель по заведённым матчам»,
заполненное значение заменяет расчёт целиком. Очки колонкой не хранятся —
выводятся из действующих wins/draws, иначе возможно состояние, где вписанные
очки противоречат вписанным победам.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

_COLUMNS = (
    "manual_tournaments",
    "manual_games",
    "manual_wins",
    "manual_draws",
    "manual_losses",
    "manual_goals_for",
    "manual_goals_against",
)


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column("teams", sa.Column(name, sa.Integer(), nullable=True))


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        op.drop_column("teams", name)
