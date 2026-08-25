"""Команда — справочник, используется в Tournament.teams."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Team(Base):
    """Карточка команды-участника турниров."""

    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Поправка к общей статистике: матчи, которых в системе нет (старые турниры).
    # Итог = расчёт по заведённым матчам + поправка, поэтому новые матчи попадают
    # в итог автоматически, а внесённая правка не устаревает.
    # None означает «поправки нет» и равносильно нулю. Значение может быть
    # отрицательным — иначе итог нельзя было бы уменьшить.
    # Очки колонкой не хранятся: выводятся из итоговых wins/draws.
    extra_tournaments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_games: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_draws: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_goals_for: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_goals_against: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
