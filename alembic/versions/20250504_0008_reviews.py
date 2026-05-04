"""reviews table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-04

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vk_comment_id", sa.BigInteger(), nullable=True),
        sa.Column("vk_topic_id", sa.BigInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("author_photo_url", sa.String(length=1024), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_reviews_vk_comment_id",
        "reviews",
        ["vk_comment_id"],
        unique=True,
        postgresql_where=sa.text("vk_comment_id IS NOT NULL"),
    )
    op.create_index(
        "ix_reviews_visible_position",
        "reviews",
        ["is_visible", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_reviews_visible_position", table_name="reviews")
    op.drop_index("ux_reviews_vk_comment_id", table_name="reviews")
    op.drop_table("reviews")
