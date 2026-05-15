"""tournament_teams: add photo

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tournament_teams",
        sa.Column("photo", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tournament_teams", "photo")
