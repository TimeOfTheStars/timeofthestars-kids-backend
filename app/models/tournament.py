"""Турнир + ассоциативная таблица tournament_teams для упорядоченных команд."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.arena import Arena
from app.models.team import Team


class TournamentTeam(Base):
    """Many-to-many tournament ↔ team с сохранением порядка + общее фото состава."""

    __tablename__ = "tournament_teams"
    # Создан миграцией 0010; объявлен здесь для совпадения metadata с БД.
    __table_args__ = (
        Index("ix_tournament_teams_tournament_position", "tournament_id", "position"),
    )

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    photo: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    team: Mapped[Team] = relationship(lazy="joined")


class Tournament(Base):
    """Турнир из раздела /turniry."""

    __tablename__ = "tournaments"
    # Создан миграцией 0010; объявлен здесь для совпадения metadata с БД.
    __table_args__ = (Index("ix_tournaments_visible_start", "is_visible", "start_date"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    age_category: Mapped[str] = mapped_column(String(32), nullable=False)
    birth_year: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    arena_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("arenas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    season: Mapped[str | None] = mapped_column(String(16), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    recordings_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Регламент из шапки бумажного протокола. Всё nullable — старые турниры не трогаем.
    game_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    period_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periods_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

    team_links: Mapped[list[TournamentTeam]] = relationship(
        cascade="all, delete-orphan",
        order_by="TournamentTeam.position",
        lazy="selectin",
    )

    arena: Mapped[Arena] = relationship(lazy="joined")

    @property
    def teams(self) -> list[Team]:
        """Команды в порядке, заданном position."""
        return [link.team for link in self.team_links]
