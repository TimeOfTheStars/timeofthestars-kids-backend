"""Admin user ORM model (личный кабинет)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.roles import ROLE_VIEWER
from app.db.base import Base


class AdminUser(Base):
    """Администратор кабинета; опционально VK user_id для личных уведомлений."""

    __tablename__ = "admin_users"
    # В БД (миграция 0002) это именованный UNIQUE-констрейнт, а не unique-индекс.
    # PostgreSQL всё равно строит под него уникальный индекс, поиск по username быстрый.
    __table_args__ = (UniqueConstraint("username", name="uq_admin_users_username"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=ROLE_VIEWER)
    vk_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
