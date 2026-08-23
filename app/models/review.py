"""Отзыв: либо вытянутый из VK обсуждения, либо созданный вручную."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Review(Base):
    """Отзыв с фронта; источник — комментарий в обсуждении VK или ручной ввод в админке."""

    __tablename__ = "reviews"
    __table_args__ = (
        # Созданы миграцией 0008; объявлены здесь для совпадения metadata с БД.
        Index(
            "ux_reviews_vk_comment_id",
            "vk_comment_id",
            unique=True,
            postgresql_where=text("vk_comment_id IS NOT NULL"),
        ),
        Index("ix_reviews_visible_position", "is_visible", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    vk_comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    vk_topic_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    author_photo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
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
