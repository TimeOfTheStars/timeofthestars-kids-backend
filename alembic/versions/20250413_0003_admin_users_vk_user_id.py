"""admin_users vk_user_id

Revision ID: 0003
Revises: 0002
Create Date: 2025-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_users", sa.Column("vk_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_users", "vk_user_id")
