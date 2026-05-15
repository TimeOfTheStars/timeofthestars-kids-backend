"""tournaments: add start_time

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("start_time", sa.Time(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tournaments", "start_time")
