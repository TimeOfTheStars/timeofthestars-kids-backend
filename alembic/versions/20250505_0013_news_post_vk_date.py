"""news_posts: add vk_post_date

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_posts",
        sa.Column("vk_post_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_news_posts_visible_position_vkdate",
        "news_posts",
        ["is_visible", "position", "vk_post_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_news_posts_visible_position_vkdate", table_name="news_posts")
    op.drop_column("news_posts", "vk_post_date")
