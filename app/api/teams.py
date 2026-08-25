"""Публичный HTTP API: справочник команд с общей статистикой."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.urls import absolutize
from app.db.session import get_db_session
from app.models.team import Team
from app.repositories import teams as teams_repo
from app.schemas.game import TeamCareerPublic, TeamPublicCard
from app.services import stats as stats_service

router = APIRouter(tags=["teams"])

_CACHE_CONTROL = "public, max-age=300"


def _career_public(c: stats_service.TeamCareer) -> TeamCareerPublic:
    return TeamCareerPublic(
        tournaments=c.tournaments,
        games=c.games,
        wins=c.wins,
        draws=c.draws,
        losses=c.losses,
        goals_for=c.goals_for,
        goals_against=c.goals_against,
        goal_diff=c.goal_diff,
        points=c.points,
    )


def _card(team: Team, career: stats_service.TeamCareer, base: str | None) -> TeamPublicCard:
    return TeamPublicCard(
        id=str(team.id),
        name=team.name,
        city=team.city,
        logo=absolutize(team.logo, base),
        description=team.description,
        stats=_career_public(career),
    )


@router.get(
    "/teams",
    response_model=list[TeamPublicCard],
    summary="Справочник команд с общей статистикой",
)
async def list_teams(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[TeamPublicCard]:
    """Статистика — действующая: часть показателей может быть вписана вручную."""
    rows = await teams_repo.list_all(session, skip=skip, limit=limit)
    response.headers["Cache-Control"] = _CACHE_CONTROL
    base = settings.public_base_url
    # Один расчёт на всех — иначе был бы N+1 по числу команд.
    stats = await stats_service.team_effective_stats(session, rows)
    return [_card(r, stats[r.id][0], base) for r in rows]


@router.get(
    "/teams/{team_id}",
    response_model=TeamPublicCard,
    summary="Команда с общей статистикой",
)
async def get_team(
    team_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> TeamPublicCard:
    row = await teams_repo.get_by_id(session, team_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Команда не найдена")
    response.headers["Cache-Control"] = _CACHE_CONTROL
    stats = await stats_service.team_effective_stats(session, [row])
    return _card(row, stats[row.id][0], settings.public_base_url)
