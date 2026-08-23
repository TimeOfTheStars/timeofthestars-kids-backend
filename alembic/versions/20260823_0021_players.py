"""players + tournament_players: справочник игроков и заявка на турнир

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-23

Аддитивно: две новые таблицы, существующие данные не затрагиваются.
tournament_players ссылается составным FK на композитный PK tournament_teams,
поэтому заявить игрока за команду, которой нет в турнире, невозможно.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column(
            "position",
            sa.Enum(
                "вратарь",
                "защитник",
                "нападающий",
                name="player_position",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("photo", sa.String(length=1024), nullable=True),
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
    )
    op.create_index("ix_players_full_name", "players", ["full_name"])

    op.create_table(
        "tournament_players",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tournament_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["tournament_id", "team_id"],
            ["tournament_teams.tournament_id", "tournament_teams.team_id"],
            name="fk_tournament_players_tournament_team",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name="fk_tournament_players_player",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tournament_id",
            "team_id",
            "player_id",
            name="uq_tournament_team_player",
        ),
    )
    # Номера в команде уникальны, но пустой номер разрешён любому числу игроков.
    op.create_index(
        "uq_tournament_team_number",
        "tournament_players",
        ["tournament_id", "team_id", "number"],
        unique=True,
        postgresql_where=sa.text("number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tournament_team_number", table_name="tournament_players")
    op.drop_table("tournament_players")
    op.drop_index("ix_players_full_name", table_name="players")
    op.drop_table("players")
