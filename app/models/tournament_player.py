"""Заявка игрока на турнир: (турнир, команда, игрок) + игровой номер."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.player import Player
from app.models.team import Team


class TournamentPlayer(Base):
    """Кто заявлен за какую команду на конкретном турнире и под каким номером.

    Номер живёт здесь, а не на игроке: от турнира к турниру и номер, и команда
    могут меняться, а карьерная статистика при этом складывается корректно.
    """

    __tablename__ = "tournament_players"
    __table_args__ = (
        # Составной FK на композитный PK tournament_teams: заявить игрока за команду,
        # которой нет в этом турнире, физически невозможно.
        ForeignKeyConstraint(
            ["tournament_id", "team_id"],
            ["tournament_teams.tournament_id", "tournament_teams.team_id"],
            ondelete="CASCADE",
            name="fk_tournament_players_tournament_team",
        ),
        UniqueConstraint(
            "tournament_id",
            "team_id",
            "player_id",
            name="uq_tournament_team_player",
        ),
        # Номера внутри команды не дублируются, но пустой номер разрешён любому числу игроков.
        Index(
            "uq_tournament_team_number",
            "tournament_id",
            "team_id",
            "number",
            unique=True,
            postgresql_where=text("number IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tournament_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    # team_id входит в составной FK на tournament_teams, поэтому связь с Team — viewonly
    # с явным primaryjoin: иначе SQLAlchemy не выведет её из ForeignKeyConstraint.
    team: Mapped[Team] = relationship(
        primaryjoin="TournamentPlayer.team_id == Team.id",
        foreign_keys="TournamentPlayer.team_id",
        lazy="joined",
        viewonly=True,
    )
