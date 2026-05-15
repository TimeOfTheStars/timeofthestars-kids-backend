"""Persistence for tournaments (с m2m teams)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tournament import Tournament, TournamentTeam


def _with_teams() -> Any:
    """Стандартная подгрузка связей: team_links → team (избегаем ленивых обращений в async)."""
    return selectinload(Tournament.team_links).selectinload(TournamentTeam.team)


async def list_visible(session: AsyncSession, *, limit: int = 500) -> list[Tournament]:
    stmt = (
        select(Tournament)
        .where(Tournament.is_visible.is_(True))
        .order_by(Tournament.start_date.desc())
        .options(_with_teams())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def list_all(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 200,
) -> list[Tournament]:
    stmt = (
        select(Tournament)
        .order_by(Tournament.start_date.desc())
        .options(_with_teams())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def get_by_id(session: AsyncSession, tournament_id: uuid.UUID) -> Tournament | None:
    stmt = (
        select(Tournament)
        .where(Tournament.id == tournament_id)
        .options(_with_teams())
    )
    result = await session.execute(stmt)
    return result.scalars().unique().one_or_none()


def _replace_team_links(
    tournament: Tournament,
    teams: list[tuple[uuid.UUID, str | None]],
) -> None:
    """Полностью переписать team_links согласно порядку (team_id, photo)."""
    tournament.team_links.clear()
    for pos, (tid, photo) in enumerate(teams):
        tournament.team_links.append(
            TournamentTeam(team_id=tid, position=pos, photo=photo),
        )


async def create_one(
    session: AsyncSession,
    *,
    fields: dict[str, Any],
    teams: list[tuple[uuid.UUID, str | None]],
) -> Tournament:
    # Связи проставляем сразу в конструкторе — иначе обращение к row.team_links
    # на свежесозданном объекте триггерит ленивую загрузку, что в async-сессии
    # роняет greenlet.
    row = Tournament(
        **fields,
        team_links=[
            TournamentTeam(team_id=tid, position=pos, photo=photo)
            for pos, (tid, photo) in enumerate(teams)
        ],
    )
    session.add(row)
    await session.commit()
    fresh = await get_by_id(session, row.id)
    assert fresh is not None
    return fresh


async def update_one(
    session: AsyncSession,
    tournament_id: uuid.UUID,
    *,
    fields: dict[str, Any],
    teams: list[tuple[uuid.UUID, str | None]] | None,
) -> Tournament | None:
    row = await get_by_id(session, tournament_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    if teams is not None:
        _replace_team_links(row, teams)
    await session.commit()
    return await get_by_id(session, tournament_id)


async def delete_one(session: AsyncSession, tournament_id: uuid.UUID) -> bool:
    stmt = delete(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all(session: AsyncSession) -> int:
    result = await session.execute(delete(Tournament))
    await session.commit()
    return int(result.rowcount or 0)
