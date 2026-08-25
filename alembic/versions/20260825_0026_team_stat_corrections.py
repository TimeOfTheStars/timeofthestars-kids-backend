"""teams: manual_* → extra_* (перезапись итога заменена на поправку)

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-25

Смена модели ручной правки статистики команды.

Было: manual_* — вписанное значение ЗАМЕНЯЛО расчёт и больше не пересчитывалось,
поэтому после нового матча цифра устаревала и её приходилось править заново.

Стало: extra_* — поправка на историю вне системы. Итог = расчёт по матчам + поправка,
то есть новые матчи попадают в итог сами, а внесённая правка сохраняется.

Только переименование: на момент миграции ни у одной команды значений не было,
поэтому переносить данные не нужно. Смысл чисел, если бы они были, изменился бы
(итог → добавка), но переименование сохраняет их как есть.
"""

from __future__ import annotations

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

_FIELDS = (
    "tournaments",
    "games",
    "wins",
    "draws",
    "losses",
    "goals_for",
    "goals_against",
)


def upgrade() -> None:
    for name in _FIELDS:
        op.alter_column("teams", f"manual_{name}", new_column_name=f"extra_{name}")


def downgrade() -> None:
    for name in _FIELDS:
        op.alter_column("teams", f"extra_{name}", new_column_name=f"manual_{name}")
