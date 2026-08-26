"""Публичный HTTP API: список турниров."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.urls import absolutize
from app.db.session import get_db_session
from app.models.tournament import Tournament
from app.repositories import games as games_repo
from app.repositories import tournaments as tournaments_repo
from app.schemas.tournament import ArenaPublic, TeamPublic, TournamentPublic

router = APIRouter(tags=["tournaments"])


def _derive_season(start: date) -> str:
    """Если сезон не задан админом — выводим из даты начала: 8–12 → текущий/след., 1–7 → пред./текущий."""
    if start.month >= 8:
        return f"{start.year}/{start.year + 1}"
    return f"{start.year - 1}/{start.year}"


def _to_public(row: Tournament, base: str | None, *, has_games: bool = False) -> TournamentPublic:
    season = row.season or _derive_season(row.start_date)
    return TournamentPublic(
        id=str(row.id),
        title=row.title,
        age_category=row.age_category,
        birth_year=row.birth_year,
        start_date=row.start_date,
        end_date=row.end_date,
        start_time=row.start_time,
        end_time=row.end_time,
        arena=ArenaPublic(
            name=row.arena.name,
            url=row.arena.url,
            address=row.arena.address,
            city=row.arena.city,
        ),
        season=season,
        description=row.description,
        url=row.url,
        recordings_url=row.recordings_url,
        game_format=row.game_format,
        period_minutes=row.period_minutes,
        periods_count=row.periods_count,
        has_games=has_games,
        teams=[
            TeamPublic(
                name=link.team.name,
                city=link.team.city,
                logo=absolutize(link.team.logo, base),
                photo=absolutize(link.photo, base),
            )
            for link in row.team_links
        ],
    )


@router.get(
    "/tournaments",
    response_model=list[TournamentPublic],
    summary="Список турниров для фронта",
)
async def list_tournaments(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> list[TournamentPublic]:
    """Голый массив турниров с camelCase-полями (см. docs/public-api.md)."""
    rows = await tournaments_repo.list_visible(session)
    response.headers["Cache-Control"] = "public, max-age=300"
    base = settings.public_base_url
    # Одним запросом на все турниры — иначе был бы N+1 по числу турниров.
    game_counts = await games_repo.counts_by_tournament(session)
    return [_to_public(r, base, has_games=game_counts.get(r.id, 0) > 0) for r in rows]
