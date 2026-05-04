"""news_posts table

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vk_owner_id", sa.BigInteger(), nullable=False),
        sa.Column("vk_post_id", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("image", sa.String(length=1024), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False, server_default=""),
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
        sa.UniqueConstraint("vk_owner_id", "vk_post_id", name="ux_news_posts_owner_post"),
    )
    op.create_index(
        "ix_news_posts_visible_position_created",
        "news_posts",
        ["is_visible", "position", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_news_posts_visible_position_created", table_name="news_posts")
    op.drop_table("news_posts")
