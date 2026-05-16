"""tournaments: add end_time

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("end_time", sa.Time(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tournaments", "end_time")
