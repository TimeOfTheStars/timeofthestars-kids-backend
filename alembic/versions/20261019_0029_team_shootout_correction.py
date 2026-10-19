"""teams: extra_shootout_losses — поправка к буллитным поражениям

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-19

Буллитные поражения входят в очки, поэтому общую статистику команды без них не
поправить: вписать «23 игры» и «13 побед» можно, а очки за старые буллитные
поражения — нет. Колонка дополняет блок extra_* и работает так же: итог = расчёт
по матчам + поправка, None равносилен нулю, значение может быть отрицательным.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("extra_shootout_losses", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "extra_shootout_losses")
