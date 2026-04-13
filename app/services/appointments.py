"""Appointment use-cases."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vk_client import VKAPIError, VKClient
from app.core.config import Settings
from app.repositories import admin_users as admin_repo
from app.repositories import appointments as appointments_repo
from app.schemas.appointment import AppointmentCreate, AppointmentResponse

logger = logging.getLogger(__name__)


async def create_appointment(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    payload: AppointmentCreate,
) -> AppointmentResponse:
    """Persist appointment and notify via VK (async end-to-end)."""
    appointment = await appointments_repo.create_appointment(
        session,
        phone=payload.phone,
        parent_name=payload.parent_name,
        child_name=payload.child_name,
        child_age=payload.child_age,
    )

    recipient_ids = await admin_repo.list_vk_notify_user_ids(session)
    if not recipient_ids:
        logger.info(
            "VK notify skipped: no active admins with vk_user_id",
            extra={"appointment_id": str(appointment.id)},
        )
        return AppointmentResponse(id=appointment.id, status="created")

    vk = VKClient(http_client, settings)
    try:
        await vk.notify_new_appointment(
            phone=payload.phone,
            parent_name=payload.parent_name,
            child_name=payload.child_name,
            child_age=payload.child_age,
            recipient_user_ids=recipient_ids,
        )
    except (VKAPIError, httpx.HTTPError) as exc:
        logger.exception(
            "Appointment saved but VK notification failed",
            extra={"appointment_id": str(appointment.id), "error": str(exc)},
        )
        return AppointmentResponse(id=appointment.id, status="created_notify_failed")

    return AppointmentResponse(id=appointment.id, status="created")
