"""Persistence for arenas."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena import Arena


async def list_all(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 200,
) -> list[Arena]:
    stmt = select(Arena).order_by(Arena.name.asc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, arena_id: uuid.UUID) -> Arena | None:
    stmt = select(Arena).where(Arena.id == arena_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_one(
    session: AsyncSession,
    *,
    name: str,
    url: str | None,
    address: str | None,
    city: str | None,
) -> Arena:
    row = Arena(name=name, url=url, address=address, city=city)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_one(
    session: AsyncSession,
    arena_id: uuid.UUID,
    fields: dict[str, Any],
) -> Arena | None:
    row = await get_by_id(session, arena_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_one(session: AsyncSession, arena_id: uuid.UUID) -> bool:
    stmt = delete(Arena).where(Arena.id == arena_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all(session: AsyncSession) -> int:
    result = await session.execute(delete(Arena))
    await session.commit()
    return int(result.rowcount or 0)
