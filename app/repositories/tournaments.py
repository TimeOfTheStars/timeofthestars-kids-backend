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


# В проекте expire_on_commit=False, поэтому объект из identity map при повторном
# select сохранил бы ранее загруженную коллекцию team_links — вместе с её прежним
# порядком. После правки position это отдавало бы старый порядок команд, хотя в БД
# всё верно. populate_existing перезагружает коллекцию с актуальным ORDER BY.
_FRESH = {"populate_existing": True}


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
        .execution_options(**_FRESH)
    )
    result = await session.execute(stmt)
    return result.scalars().unique().one_or_none()


def _sync_team_links(
    tournament: Tournament,
    teams: list[tuple[uuid.UUID, str | None]],
) -> None:
    """Привести team_links к списку (team_id, photo), НЕ пересоздавая уцелевшие связи.

    Раньше здесь был clear() + append(), то есть физический DELETE+INSERT всех строк
    tournament_teams на каждое сохранение турнира (админка всегда присылает полный
    массив команд). На пару (tournament_id, team_id) теперь ссылаются заявка игроков
    (ON DELETE CASCADE) и матчи (ON DELETE RESTRICT), поэтому пересоздание либо
    снесло бы заявку, либо упало бы на FK. Обновляем на месте: удаляем только
    исчезнувшие команды, вставляем только новые, остальным правим position/photo.
    """
    existing = {link.team_id: link for link in tournament.team_links}
    wanted = {tid for tid, _ in teams}

    for link in list(tournament.team_links):
        if link.team_id not in wanted:
            tournament.team_links.remove(link)

    for pos, (tid, photo) in enumerate(teams):
        link = existing.get(tid)
        if link is None:
            tournament.team_links.append(
                TournamentTeam(team_id=tid, position=pos, photo=photo),
            )
        else:
            link.position = pos
            link.photo = photo


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
        _sync_team_links(row, teams)
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
