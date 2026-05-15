"""Persistence для заявок на турнир (игрок + команда)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tournament_application import (
    TournamentPlayerApplication,
    TournamentTeamApplication,
)


# ----- Player -----


async def create_player(
    session: AsyncSession,
    *,
    parent_name: str,
    child_name: str,
    child_age: int,
    phone: str,
) -> TournamentPlayerApplication:
    row = TournamentPlayerApplication(
        parent_name=parent_name,
        child_name=child_name,
        child_age=child_age,
        phone=phone,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_players(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[TournamentPlayerApplication]:
    stmt = (
        select(TournamentPlayerApplication)
        .order_by(TournamentPlayerApplication.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_player(session: AsyncSession, app_id: uuid.UUID) -> bool:
    stmt = delete(TournamentPlayerApplication).where(TournamentPlayerApplication.id == app_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all_players(session: AsyncSession) -> int:
    result = await session.execute(delete(TournamentPlayerApplication))
    await session.commit()
    return int(result.rowcount or 0)


# ----- Team -----


async def create_team(
    session: AsyncSession,
    *,
    team_name: str,
    city: str,
    age_category: str,
    coach_name: str,
    phone: str,
    comment: str | None,
) -> TournamentTeamApplication:
    row = TournamentTeamApplication(
        team_name=team_name,
        city=city,
        age_category=age_category,
        coach_name=coach_name,
        phone=phone,
        comment=comment,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_teams(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[TournamentTeamApplication]:
    stmt = (
        select(TournamentTeamApplication)
        .order_by(TournamentTeamApplication.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_team(session: AsyncSession, app_id: uuid.UUID) -> bool:
    stmt = delete(TournamentTeamApplication).where(TournamentTeamApplication.id == app_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all_teams(session: AsyncSession) -> int:
    result = await session.execute(delete(TournamentTeamApplication))
    await session.commit()
    return int(result.rowcount or 0)
