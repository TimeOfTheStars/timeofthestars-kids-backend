"""admin_users role

Revision ID: 0005
Revises: 0004
Create Date: 2025-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("role", sa.String(length=32), server_default="admin", nullable=False),
    )
    op.alter_column(
        "admin_users",
        "role",
        server_default="viewer",
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_column("admin_users", "role")
