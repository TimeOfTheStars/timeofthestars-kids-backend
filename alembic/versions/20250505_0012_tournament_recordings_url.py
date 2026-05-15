"""tournaments: add recordings_url

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("recordings_url", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tournaments", "recordings_url")
