"""Матч турнира, строки участия игроков и таймлайн голов.

Доктрина (унаследована из timeofthestars-backend-v2): сырые данные — единственный
источник истины. Таблица, бомбардиры и личная статистика считаются на лету
в app/services/stats.py; никаких хранимых счётчиков, кроме производных
goals/assists на строке участия, которые перезаписываются из событий при каждом
сохранении протокола.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.player import Player
from app.models.team import Team

# Пока единственный тип события. native_enum=False даёт обычный VARCHAR,
# поэтому добавить штрафы или буллиты позже — правка кода без миграции типа.
GAME_EVENT_TYPES = ("goal",)


class GamePlayerStat(Base):
    """Строка протокола: участие игрока в матче + производные голы/передачи.

    Само наличие строки означает «этот игрок играл в этом матче» — так считаются «И».
    team_id денормализован сюда, чтобы разбивка по командам была верной у игрока,
    менявшего команду между турнирами.
    """

    __tablename__ = "game_player_stats"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_game_player"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_goalie: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Минуты вратаря в этом матче, вписанные руками. Нужны, когда у команды было
    # два вратаря: ПШ/ОБ из табло между ними не делятся, а время известно.
    # None — минуты считаются по регламенту для единственного вратаря команды.
    minutes_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Производные: перезаписываются из game_events в save_protocol().
    goals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assists: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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

    player: Mapped[Player] = relationship(lazy="joined")
    team: Mapped[Team] = relationship(lazy="joined")


class GameEvent(Base):
    """Событие таймлайна — сейчас только гол («ВЗЯТИЕ ВОРОТ» бумажного протокола).

    time_seconds — время ВНУТРИ периода, period вводится вручную (на бумаге его нет).
    Порядок в пределах периода задаёт sort_order — это колонка «№» бланка; времена
    в бумажном протоколе не отсортированы, поэтому сортировать по времени нельзя.
    """

    __tablename__ = "game_events"
    __table_args__ = (
        CheckConstraint(
            "assist1_player_id IS NULL OR assist1_player_id <> player_id",
            name="ck_game_events_assist1_not_scorer",
        ),
        CheckConstraint(
            "assist2_player_id IS NULL OR assist2_player_id <> player_id",
            name="ck_game_events_assist2_not_scorer",
        ),
        CheckConstraint(
            "assist2_player_id IS NULL OR assist1_player_id IS NOT NULL",
            name="ck_game_events_assist2_needs_assist1",
        ),
        CheckConstraint(
            "assist1_player_id IS NULL "
            "OR assist2_player_id IS NULL "
            "OR assist1_player_id <> assist2_player_id",
            name="ck_game_events_assists_distinct",
        ),
        CheckConstraint("time_seconds >= 0", name="ck_game_events_time_non_negative"),
        CheckConstraint("period >= 1", name="ck_game_events_period_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        Enum(*GAME_EVENT_TYPES, name="game_event_type", native_enum=False, length=32),
        nullable=False,
        default="goal",
    )
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SET NULL, а не CASCADE: удаление ассистента не должно уносить сам гол.
    assist1_player_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
    )
    assist2_player_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    @property
    def assist_ids(self) -> list[uuid.UUID]:
        """Непустые ассистенты в порядке бланка — удобно для подсчёта передач."""
        return [a for a in (self.assist1_player_id, self.assist2_player_id) if a is not None]


class Game(Base):
    """Матч турнира. Стадий нет — плоский список, все сыгранные матчи идут в таблицу."""

    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("team_a_id <> team_b_id", name="ck_games_teams_distinct"),
        # Обе команды обязаны быть заявлены в этот турнир. RESTRICT: убрать из турнира
        # команду, у которой есть матчи, нельзя — матчи не должны исчезать молча.
        ForeignKeyConstraint(
            ["tournament_id", "team_a_id"],
            ["tournament_teams.tournament_id", "tournament_teams.team_id"],
            ondelete="RESTRICT",
            name="fk_games_tournament_team_a",
        ),
        ForeignKeyConstraint(
            ["tournament_id", "team_b_id"],
            ["tournament_teams.tournament_id", "tournament_teams.team_id"],
            ondelete="RESTRICT",
            name="fk_games_tournament_team_b",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Порядок и нумерация матчей внутри турнира — «МАТЧ №» бумажного протокола.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    team_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    team_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # «Табло матча»: голы и броски по командам.
    score_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[time | None] = mapped_column(Time, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    scan: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Выводится сервисом (оба счёта заданы), клиент его не присылает.
    is_finished: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    team_a: Mapped[Team] = relationship(
        primaryjoin="Game.team_a_id == Team.id",
        foreign_keys="Game.team_a_id",
        lazy="joined",
        viewonly=True,
    )
    team_b: Mapped[Team] = relationship(
        primaryjoin="Game.team_b_id == Team.id",
        foreign_keys="Game.team_b_id",
        lazy="joined",
        viewonly=True,
    )
    stat_lines: Mapped[list[GamePlayerStat]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # Порядок задан в маппинге, чтобы API и админка сортировали одинаково.
    events: Mapped[list[GameEvent]] = relationship(
        cascade="all, delete-orphan",
        order_by="(GameEvent.period, GameEvent.sort_order, GameEvent.created_at)",
        lazy="selectin",
    )
