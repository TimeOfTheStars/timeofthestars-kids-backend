"""Persistence for players (глобальный справочник игроков)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player


async def list_all(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 500,
    search: str | None = None,
) -> list[Player]:
    stmt = select(Player).order_by(Player.full_name.asc())
    if search:
        stmt = stmt.where(Player.full_name.ilike(f"%{search.strip()}%"))
    stmt = stmt.offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_all(session: AsyncSession, *, search: str | None = None) -> int:
    stmt = select(func.count(Player.id))
    if search:
        stmt = stmt.where(Player.full_name.ilike(f"%{search.strip()}%"))
    return int((await session.execute(stmt)).scalar_one())


async def get_by_id(session: AsyncSession, player_id: uuid.UUID) -> Player | None:
    result = await session.execute(select(Player).where(Player.id == player_id))
    return result.scalar_one_or_none()


async def get_by_ids(session: AsyncSession, player_ids: list[uuid.UUID]) -> list[Player]:
    if not player_ids:
        return []
    result = await session.execute(select(Player).where(Player.id.in_(player_ids)))
    return list(result.scalars().all())


async def create_one(
    session: AsyncSession,
    *,
    full_name: str,
    birth_date: Any = None,
    position: str | None = None,
    photo: str | None = None,
) -> Player:
    row = Player(full_name=full_name, birth_date=birth_date, position=position, photo=photo)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_one(
    session: AsyncSession,
    player_id: uuid.UUID,
    fields: dict[str, Any],
) -> Player | None:
    row = await get_by_id(session, player_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_one(session: AsyncSession, player_id: uuid.UUID) -> bool:
    result = await session.execute(delete(Player).where(Player.id == player_id))
    await session.commit()
    return bool(result.rowcount)
