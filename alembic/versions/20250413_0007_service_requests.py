"""service_requests table

Revision ID: 0007
Revises: 0006
Create Date: 2025-04-13

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("parent_name", sa.String(length=255), nullable=False),
        sa.Column("child_name", sa.String(length=255), nullable=False),
        sa.Column("child_age", sa.Integer(), nullable=False),
        sa.Column("service", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("service_requests")
