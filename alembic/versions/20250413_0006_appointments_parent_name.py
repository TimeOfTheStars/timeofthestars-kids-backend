"""appointments parent_name

Revision ID: 0006
Revises: 0005
Create Date: 2025-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("parent_name", sa.String(length=255), server_default="", nullable=False),
    )
    op.alter_column(
        "appointments",
        "parent_name",
        server_default=None,
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_column("appointments", "parent_name")
