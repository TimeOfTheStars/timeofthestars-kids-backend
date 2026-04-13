"""Use-cases for service requests."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vk_client import VKAPIError, VKClient
from app.core.config import Settings
from app.repositories import admin_users as admin_repo
from app.repositories import service_requests as service_requests_repo
from app.schemas.service_request import ServiceRequestCreate, ServiceRequestResponse

logger = logging.getLogger(__name__)


async def create_service_request(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    payload: ServiceRequestCreate,
) -> ServiceRequestResponse:
    row = await service_requests_repo.create_service_request(
        session,
        phone=payload.phone,
        parent_name=payload.parent_name,
        child_name=payload.child_name,
        child_age=payload.child_age,
        service=payload.service,
    )

    recipient_ids = await admin_repo.list_vk_notify_user_ids(session)
    if not recipient_ids:
        logger.info(
            "VK notify skipped: no active admins with vk_user_id",
            extra={"service_request_id": str(row.id)},
        )
        return ServiceRequestResponse(id=row.id, status="created")

    vk = VKClient(http_client, settings)
    try:
        await vk.notify_new_service_request(
            phone=payload.phone,
            parent_name=payload.parent_name,
            child_name=payload.child_name,
            child_age=payload.child_age,
            service=payload.service,
            recipient_user_ids=recipient_ids,
        )
    except (VKAPIError, httpx.HTTPError) as exc:
        logger.exception(
            "Service request saved but VK notification failed",
            extra={"service_request_id": str(row.id), "error": str(exc)},
        )
        return ServiceRequestResponse(id=row.id, status="created_notify_failed")

    return ServiceRequestResponse(id=row.id, status="created")
