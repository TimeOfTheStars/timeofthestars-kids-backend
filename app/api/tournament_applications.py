"""Публичные эндпоинты заявок на турнир (игрок / команда)."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.tournament_application import (
    TournamentPlayerApplicationCreate,
    TournamentPlayerApplicationResponse,
    TournamentTeamApplicationCreate,
    TournamentTeamApplicationResponse,
)
from app.services import tournament_applications as service

router = APIRouter(tags=["tournament-applications"])


def _get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@router.post(
    "/tournament-applications/player",
    response_model=TournamentPlayerApplicationResponse,
    status_code=201,
    summary="Заявка на участие в турнире — игрок",
)
async def create_player_application(
    body: TournamentPlayerApplicationCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> TournamentPlayerApplicationResponse:
    return await service.create_player_application(session, http_client, settings, body)


@router.post(
    "/tournament-applications/team",
    response_model=TournamentTeamApplicationResponse,
    status_code=201,
    summary="Заявка на участие в турнире — команда",
)
async def create_team_application(
    body: TournamentTeamApplicationCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> TournamentTeamApplicationResponse:
    return await service.create_team_application(session, http_client, settings, body)
