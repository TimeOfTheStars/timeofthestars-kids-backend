"""Persistence for games (+ строки участия и события)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game import Game, GameEvent, GamePlayerStat


def _with_protocol() -> tuple[Any, ...]:
    """Подгрузка протокола целиком: строки участия и события (без ленивых обращений в async)."""
    return (
        selectinload(Game.stat_lines).selectinload(GamePlayerStat.player),
        selectinload(Game.events),
    )


# В проекте expire_on_commit=False, поэтому объект, уже лежащий в identity map,
# при повторном select сохранил бы РАНЕЕ загруженные коллекции (stat_lines/events).
# После сохранения протокола это отдавало бы устаревший таймлайн, хотя в БД всё верно.
# populate_existing заставляет перезагрузить и объект, и его eager-коллекции.
_FRESH = {"populate_existing": True}


async def list_for_tournament(session: AsyncSession, tournament_id: uuid.UUID) -> list[Game]:
    stmt = (
        select(Game)
        .where(Game.tournament_id == tournament_id)
        .order_by(Game.position.asc(), Game.date.asc(), Game.time.asc().nullsfirst())
        .options(*_with_protocol())
        .execution_options(**_FRESH)
    )
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def get_by_id(session: AsyncSession, game_id: uuid.UUID) -> Game | None:
    stmt = (
        select(Game)
        .where(Game.id == game_id)
        .options(*_with_protocol())
        .execution_options(**_FRESH)
    )
    result = await session.execute(stmt)
    return result.scalars().unique().one_or_none()


async def counts_by_tournament(session: AsyncSession) -> dict[uuid.UUID, int]:
    """Число ЗАВЕДЁННЫХ матчей по всем турнирам одним запросом (для списка /tournaments).

    Считаются все матчи, а не только сыгранные: флаг hasGames говорит фронту, что
    турнир можно открыть и показать расписание, даже когда результатов ещё нет.
    """
    stmt = select(Game.tournament_id, func.count(Game.id)).group_by(Game.tournament_id)
    result = await session.execute(stmt)
    return {tid: int(cnt) for tid, cnt in result.all()}


async def next_position(session: AsyncSession, tournament_id: uuid.UUID) -> int:
    """Следующий «МАТЧ №» внутри турнира."""
    stmt = select(func.coalesce(func.max(Game.position), 0)).where(
        Game.tournament_id == tournament_id,
    )
    return int((await session.execute(stmt)).scalar_one()) + 1


async def create_one(session: AsyncSession, *, fields: dict[str, Any]) -> Game:
    row = Game(**fields)
    session.add(row)
    await session.commit()
    fresh = await get_by_id(session, row.id)
    assert fresh is not None
    return fresh


async def update_one(
    session: AsyncSession,
    game_id: uuid.UUID,
    fields: dict[str, Any],
) -> Game | None:
    row = await get_by_id(session, game_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    # Матч считается сыгранным, когда заполнены оба счёта. Клиент этот флаг не присылает.
    row.is_finished = row.score_a is not None and row.score_b is not None
    await session.commit()
    return await get_by_id(session, game_id)


async def delete_one(session: AsyncSession, game_id: uuid.UUID) -> bool:
    result = await session.execute(delete(Game).where(Game.id == game_id))
    await session.commit()
    return bool(result.rowcount)


async def team_ids_with_games(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Команды турнира, у которых есть хотя бы один матч (обе стороны)."""
    stmt = select(Game.team_a_id, Game.team_b_id).where(Game.tournament_id == tournament_id)
    result = await session.execute(stmt)
    out: set[uuid.UUID] = set()
    for a, b in result.all():
        out.add(a)
        out.add(b)
    return out


async def events_for_game(session: AsyncSession, game_id: uuid.UUID) -> list[GameEvent]:
    stmt = (
        select(GameEvent)
        .where(GameEvent.game_id == game_id)
        .order_by(GameEvent.period, GameEvent.sort_order, GameEvent.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
