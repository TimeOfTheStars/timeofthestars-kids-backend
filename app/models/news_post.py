"""Новость (пост из VK) для секции «Новости» на фронте."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsPost(Base):
    """Превью VK-поста, отображаемое в блоке «Новости»."""

    __tablename__ = "news_posts"
    __table_args__ = (
        UniqueConstraint("vk_owner_id", "vk_post_id", name="ux_news_posts_owner_post"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    vk_owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vk_post_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    image: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
