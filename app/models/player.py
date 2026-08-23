"""Игрок — глобальный справочник. Номер и команда живут на заявке (tournament_players)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Амплуа хранятся русскими строками — так же, как в timeofthestars-backend-v2.
PLAYER_POSITIONS = ("вратарь", "защитник", "нападающий")


class Player(Base):
    """Ребёнок-хоккеист. Один на все турниры, статистика складывается по нему."""

    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # native_enum=False → обычный VARCHAR с CHECK: добавить амплуа можно без миграции типа.
    position: Mapped[str | None] = mapped_column(
        Enum(*PLAYER_POSITIONS, name="player_position", native_enum=False, length=32),
        nullable=True,
    )
    photo: Mapped[str | None] = mapped_column(String(1024), nullable=True)
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
