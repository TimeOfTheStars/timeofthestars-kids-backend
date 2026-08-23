"""Persistence for tournament_players (заявка игроков на турнир)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.models.player import Player
from app.models.tournament_player import TournamentPlayer


async def list_for_tournament(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> list[TournamentPlayer]:
    """Вся заявка турнира: сначала по команде, затем по номеру (пустые номера в конец)."""
    # Один join на players через relationship + contains_eager: и сортировка по ФИО,
    # и подгрузка игрока без второго join, который добавил бы joinedload.
    stmt = (
        select(TournamentPlayer)
        .where(TournamentPlayer.tournament_id == tournament_id)
        .join(TournamentPlayer.player)
        .options(contains_eager(TournamentPlayer.player), joinedload(TournamentPlayer.team))
        .order_by(
            TournamentPlayer.team_id,
            TournamentPlayer.number.asc().nullslast(),
            Player.full_name.asc(),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def get_by_id(session: AsyncSession, entry_id: uuid.UUID) -> TournamentPlayer | None:
    stmt = (
        select(TournamentPlayer)
        .where(TournamentPlayer.id == entry_id)
        .options(joinedload(TournamentPlayer.player), joinedload(TournamentPlayer.team))
    )
    result = await session.execute(stmt)
    return result.scalars().unique().one_or_none()


async def list_team_ids_with_players(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Команды турнира, у которых есть хотя бы один заявленный игрок."""
    stmt = (
        select(TournamentPlayer.team_id)
        .where(TournamentPlayer.tournament_id == tournament_id)
        .distinct()
    )
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def registered_pairs(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Множество (player_id, team_id) заявки — для валидации протокола одним запросом."""
    stmt = select(TournamentPlayer.player_id, TournamentPlayer.team_id).where(
        TournamentPlayer.tournament_id == tournament_id,
    )
    result = await session.execute(stmt)
    return {(pid, tid) for pid, tid in result.all()}


async def add_many(
    session: AsyncSession,
    *,
    tournament_id: uuid.UUID,
    team_id: uuid.UUID,
    entries: list[tuple[uuid.UUID, int | None]],
) -> list[TournamentPlayer]:
    """Массово заявить игроков (player_id, number). Уже заявленные пропускаются."""
    existing = await session.execute(
        select(TournamentPlayer.player_id).where(
            TournamentPlayer.tournament_id == tournament_id,
            TournamentPlayer.team_id == team_id,
        ),
    )
    already = set(existing.scalars().all())
    created: list[TournamentPlayer] = []
    for player_id, number in entries:
        if player_id in already:
            continue
        already.add(player_id)
        row = TournamentPlayer(
            tournament_id=tournament_id,
            team_id=team_id,
            player_id=player_id,
            number=number,
        )
        session.add(row)
        created.append(row)
    await session.commit()
    return [r for r in [await get_by_id(session, c.id) for c in created] if r is not None]


async def update_one(
    session: AsyncSession,
    entry_id: uuid.UUID,
    fields: dict[str, Any],
) -> TournamentPlayer | None:
    row = await get_by_id(session, entry_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    await session.commit()
    return await get_by_id(session, entry_id)


async def delete_one(session: AsyncSession, entry_id: uuid.UUID) -> bool:
    result = await session.execute(delete(TournamentPlayer).where(TournamentPlayer.id == entry_id))
    await session.commit()
    return bool(result.rowcount)
