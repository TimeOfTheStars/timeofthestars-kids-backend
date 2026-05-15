"""Use-cases для заявок на турнир (игрок / команда)."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vk_client import VKAPIError, VKClient
from app.core.config import Settings
from app.repositories import admin_users as admin_repo
from app.repositories import tournament_applications as repo
from app.schemas.tournament_application import (
    TournamentPlayerApplicationCreate,
    TournamentPlayerApplicationResponse,
    TournamentTeamApplicationCreate,
    TournamentTeamApplicationResponse,
)

logger = logging.getLogger(__name__)


async def create_player_application(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    payload: TournamentPlayerApplicationCreate,
) -> TournamentPlayerApplicationResponse:
    row = await repo.create_player(
        session,
        parent_name=payload.parent_name,
        child_name=payload.child_name,
        child_age=payload.child_age,
        phone=payload.phone,
    )

    recipient_ids = await admin_repo.list_vk_notify_user_ids(session)
    if not recipient_ids:
        logger.info(
            "VK notify skipped: no active admins with vk_user_id",
            extra={"tournament_player_application_id": str(row.id)},
        )
        return TournamentPlayerApplicationResponse(id=row.id, status="created")

    vk = VKClient(http_client, settings)
    try:
        await vk.notify_new_tournament_player_application(
            parent_name=payload.parent_name,
            child_name=payload.child_name,
            child_age=payload.child_age,
            phone=payload.phone,
            recipient_user_ids=recipient_ids,
        )
    except (VKAPIError, httpx.HTTPError) as exc:
        logger.exception(
            "Player application saved but VK notification failed",
            extra={"tournament_player_application_id": str(row.id), "error": str(exc)},
        )
        return TournamentPlayerApplicationResponse(id=row.id, status="created_notify_failed")

    return TournamentPlayerApplicationResponse(id=row.id, status="created")


async def create_team_application(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    payload: TournamentTeamApplicationCreate,
) -> TournamentTeamApplicationResponse:
    row = await repo.create_team(
        session,
        team_name=payload.team_name,
        city=payload.city,
        age_category=payload.age_category,
        coach_name=payload.coach_name,
        phone=payload.phone,
        comment=payload.comment,
    )

    recipient_ids = await admin_repo.list_vk_notify_user_ids(session)
    if not recipient_ids:
        logger.info(
            "VK notify skipped: no active admins with vk_user_id",
            extra={"tournament_team_application_id": str(row.id)},
        )
        return TournamentTeamApplicationResponse(id=row.id, status="created")

    vk = VKClient(http_client, settings)
    try:
        await vk.notify_new_tournament_team_application(
            team_name=payload.team_name,
            city=payload.city,
            age_category=payload.age_category,
            coach_name=payload.coach_name,
            phone=payload.phone,
            comment=payload.comment,
            recipient_user_ids=recipient_ids,
        )
    except (VKAPIError, httpx.HTTPError) as exc:
        logger.exception(
            "Team application saved but VK notification failed",
            extra={"tournament_team_application_id": str(row.id), "error": str(exc)},
        )
        return TournamentTeamApplicationResponse(id=row.id, status="created_notify_failed")

    return TournamentTeamApplicationResponse(id=row.id, status="created")
