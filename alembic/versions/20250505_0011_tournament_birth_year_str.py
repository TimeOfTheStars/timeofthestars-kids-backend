"""tournaments.birth_year: INTEGER -> VARCHAR(32)

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tournaments",
        "birth_year",
        type_=sa.String(length=32),
        existing_type=sa.Integer(),
        existing_nullable=True,
        postgresql_using="birth_year::text",
    )


def downgrade() -> None:
    op.alter_column(
        "tournaments",
        "birth_year",
        type_=sa.Integer(),
        existing_type=sa.String(length=32),
        existing_nullable=True,
        postgresql_using="NULLIF(regexp_replace(birth_year, '\\D', '', 'g'), '')::integer",
    )
