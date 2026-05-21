"""arenas: dictionary table + tournaments.arena_id (replaces location string)

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-21

Каждая уникальная строка `tournaments.location` превращается в запись `arenas`
(name = location), на которую турниры перепривязываются по arena_id. После этого
колонка `location` дропается. Админ потом редактирует у автоматически созданных
арен url/address/city руками.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "arenas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
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

    op.add_column(
        "tournaments",
        sa.Column("arena_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Перенос данных: каждая уникальная location → новая arena, турниры перепривязываются.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT DISTINCT location FROM tournaments")).fetchall()
    for (loc,) in rows:
        arena_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO arenas (id, name, created_at, updated_at) "
                "VALUES (:id, :name, now(), now())"
            ),
            {"id": arena_id, "name": loc},
        )
        conn.execute(
            sa.text("UPDATE tournaments SET arena_id = :aid WHERE location = :name"),
            {"aid": arena_id, "name": loc},
        )

    op.alter_column("tournaments", "arena_id", nullable=False)
    op.create_foreign_key(
        "fk_tournaments_arena_id",
        "tournaments",
        "arenas",
        ["arena_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("tournaments", "location")


def downgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("location", sa.String(length=512), nullable=True),
    )
    op.execute(
        "UPDATE tournaments t SET location = a.name "
        "FROM arenas a WHERE a.id = t.arena_id"
    )
    op.alter_column("tournaments", "location", nullable=False)
    op.drop_constraint("fk_tournaments_arena_id", "tournaments", type_="foreignkey")
    op.drop_column("tournaments", "arena_id")
    op.drop_table("arenas")
