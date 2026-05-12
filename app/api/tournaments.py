"""Публичный HTTP API: список турниров."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.tournament import Tournament
from app.repositories import tournaments as tournaments_repo
from app.schemas.tournament import TeamPublic, TournamentPublic

router = APIRouter(tags=["tournaments"])


def _derive_season(start: date) -> str:
    """Если сезон не задан админом — выводим из даты начала: 8–12 → текущий/след., 1–7 → пред./текущий."""
    if start.month >= 8:
        return f"{start.year}/{start.year + 1}"
    return f"{start.year - 1}/{start.year}"


def _to_public(row: Tournament) -> TournamentPublic:
    season = row.season or _derive_season(row.start_date)
    return TournamentPublic(
        id=str(row.id),
        title=row.title,
        age_category=row.age_category,
        birth_year=row.birth_year,
        start_date=row.start_date,
        end_date=row.end_date,
        location=row.location,
        city=row.city,
        season=season,
        description=row.description,
        url=row.url,
        teams=[TeamPublic(name=t.name, logo=t.logo) for t in row.teams],
    )


@router.get(
    "/tournaments",
    response_model=list[TournamentPublic],
    summary="Список турниров для фронта",
)
async def list_tournaments(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    response: Response,
) -> list[TournamentPublic]:
    """Голый массив турниров с camelCase-полями (см. tournaments-api.md, вариант A)."""
    rows = await tournaments_repo.list_visible(session)
    response.headers["Cache-Control"] = "public, max-age=300"
    return [_to_public(r) for r in rows]
