"""Persistence for teams."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team


async def list_all(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 200,
) -> list[Team]:
    stmt = select(Team).order_by(Team.name.asc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, team_id: uuid.UUID) -> Team | None:
    stmt = select(Team).where(Team.id == team_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_ids(session: AsyncSession, team_ids: list[uuid.UUID]) -> list[Team]:
    if not team_ids:
        return []
    stmt = select(Team).where(Team.id.in_(team_ids))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_one(
    session: AsyncSession,
    *,
    name: str,
    logo: str | None,
) -> Team:
    row = Team(name=name, logo=logo)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_one(
    session: AsyncSession,
    team_id: uuid.UUID,
    fields: dict[str, Any],
) -> Team | None:
    row = await get_by_id(session, team_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_one(session: AsyncSession, team_id: uuid.UUID) -> bool:
    stmt = delete(Team).where(Team.id == team_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)
