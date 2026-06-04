"""question_requests: rename phone→contact (255), add question (NOT NULL '')

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-05

`phone` переименовывается в `contact` и расширяется до 255 символов
(теперь принимает почту/телеграм/любой контакт). Существующие данные
сохраняются — это просто переименование колонки + расширение типа.
Поле `question` добавляется как NOT NULL DEFAULT '', чтобы старые записи
не падали при выборке.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "question_requests",
        "phone",
        new_column_name="contact",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.add_column(
        "question_requests",
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("question_requests", "question")
    op.alter_column(
        "question_requests",
        "contact",
        new_column_name="phone",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
