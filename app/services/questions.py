"""Создание записи вопроса и уведомление в VK."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vk_client import VKAPIError, VKClient
from app.core.config import Settings
from app.repositories import admin_users as admin_repo
from app.repositories import questions as questions_repo
from app.schemas.question import QuestionCreate, QuestionResponse

logger = logging.getLogger(__name__)


async def create_question(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    payload: QuestionCreate,
) -> QuestionResponse:
    row = await questions_repo.create_question(
        session,
        full_name=payload.full_name,
        phone=payload.phone,
    )

    recipient_ids = await admin_repo.list_vk_notify_user_ids(session)
    if not recipient_ids:
        logger.info(
            "VK notify skipped (question): no active users with vk_user_id",
            extra={"question_id": str(row.id)},
        )
        return QuestionResponse(id=row.id, status="created")

    vk = VKClient(http_client, settings)
    try:
        await vk.notify_new_question(
            full_name=payload.full_name,
            phone=payload.phone,
            recipient_user_ids=recipient_ids,
        )
    except (VKAPIError, httpx.HTTPError) as exc:
        logger.exception(
            "Question saved but VK notification failed",
            extra={"question_id": str(row.id), "error": str(exc)},
        )
        return QuestionResponse(id=row.id, status="created_notify_failed")

    return QuestionResponse(id=row.id, status="created")
