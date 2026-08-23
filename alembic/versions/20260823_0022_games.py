"""games + game_player_stats + game_events: матчи, участие игроков, таймлайн голов

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-23

Аддитивно: три новые таблицы. Обе команды матча обязаны быть заявлены в турнир
(составные FK на tournament_teams с RESTRICT — убрать из турнира команду,
у которой есть матчи, нельзя).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tournament_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score_a", sa.Integer(), nullable=True),
        sa.Column("score_b", sa.Integer(), nullable=True),
        sa.Column("shots_a", sa.Integer(), nullable=True),
        sa.Column("shots_b", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time", sa.Time(), nullable=True),
        sa.Column("video_url", sa.String(length=1024), nullable=True),
        sa.Column("scan", sa.String(length=1024), nullable=True),
        sa.Column("is_finished", sa.Boolean(), nullable=False, server_default=sa.false()),
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
            ["tournament_id"],
            ["tournaments.id"],
            name="fk_games_tournament",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tournament_id", "team_a_id"],
            ["tournament_teams.tournament_id", "tournament_teams.team_id"],
            name="fk_games_tournament_team_a",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tournament_id", "team_b_id"],
            ["tournament_teams.tournament_id", "tournament_teams.team_id"],
            name="fk_games_tournament_team_b",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("team_a_id <> team_b_id", name="ck_games_teams_distinct"),
    )
    op.create_index("ix_games_tournament_id", "games", ["tournament_id"])

    op.create_table(
        "game_player_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_goalie", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("goals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists", sa.Integer(), nullable=False, server_default="0"),
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
            ["game_id"], ["games.id"], name="fk_game_player_stats_game", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name="fk_game_player_stats_player",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name="fk_game_player_stats_team", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("game_id", "player_id", name="uq_game_player"),
    )
    op.create_index("ix_game_player_stats_game_id", "game_player_stats", ["game_id"])

    op.create_table(
        "game_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum("goal", name="game_event_type", native_enum=False, length=32),
            nullable=False,
            server_default="goal",
        ),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assist1_player_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assist2_player_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["game_id"], ["games.id"], name="fk_game_events_game", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name="fk_game_events_team", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name="fk_game_events_player", ondelete="CASCADE"
        ),
        # SET NULL: удаление ассистента не должно уносить сам гол.
        sa.ForeignKeyConstraint(
            ["assist1_player_id"],
            ["players.id"],
            name="fk_game_events_assist1",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assist2_player_id"],
            ["players.id"],
            name="fk_game_events_assist2",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "assist1_player_id IS NULL OR assist1_player_id <> player_id",
            name="ck_game_events_assist1_not_scorer",
        ),
        sa.CheckConstraint(
            "assist2_player_id IS NULL OR assist2_player_id <> player_id",
            name="ck_game_events_assist2_not_scorer",
        ),
        sa.CheckConstraint(
            "assist2_player_id IS NULL OR assist1_player_id IS NOT NULL",
            name="ck_game_events_assist2_needs_assist1",
        ),
        sa.CheckConstraint(
            "assist1_player_id IS NULL "
            "OR assist2_player_id IS NULL "
            "OR assist1_player_id <> assist2_player_id",
            name="ck_game_events_assists_distinct",
        ),
        sa.CheckConstraint("time_seconds >= 0", name="ck_game_events_time_non_negative"),
        sa.CheckConstraint("period >= 1", name="ck_game_events_period_positive"),
    )
    op.create_index("ix_game_events_game_id", "game_events", ["game_id"])


def downgrade() -> None:
    op.drop_index("ix_game_events_game_id", table_name="game_events")
    op.drop_table("game_events")
    op.drop_index("ix_game_player_stats_game_id", table_name="game_player_stats")
    op.drop_table("game_player_stats")
    op.drop_index("ix_games_tournament_id", table_name="games")
    op.drop_table("games")
