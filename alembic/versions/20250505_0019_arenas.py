"""arenas: dictionary table + tournaments.arena_id (replaces location string + city)

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-21

Каждая уникальная строка `tournaments.location` превращается в запись `arenas`
(name = location, city = первый встретившийся city у турниров с такой location),
на которую турниры перепривязываются по arena_id. После этого колонки `location`
и `city` у tournaments дропаются — город теперь живёт только на арене.
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

    # Перенос данных: каждая уникальная location → новая arena (city = MIN(city)
    # среди турниров с такой location, чтобы захватить заполненный город,
    # если он есть). Турниры перепривязываются по arena_id.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT location, MIN(city) AS city FROM tournaments GROUP BY location")
    ).fetchall()
    for loc, city in rows:
        arena_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO arenas (id, name, city, created_at, updated_at) "
                "VALUES (:id, :name, :city, now(), now())"
            ),
            {"id": arena_id, "name": loc, "city": city},
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
    op.drop_column("tournaments", "city")


def downgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("location", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "tournaments",
        sa.Column("city", sa.String(length=255), nullable=True),
    )
    op.execute(
        "UPDATE tournaments t SET location = a.name, city = a.city "
        "FROM arenas a WHERE a.id = t.arena_id"
    )
    op.alter_column("tournaments", "location", nullable=False)
    op.drop_constraint("fk_tournaments_arena_id", "tournaments", type_="foreignkey")
    op.drop_column("tournaments", "arena_id")
    op.drop_table("arenas")
