"""Appointments HTTP API."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.services import appointments as appointment_service

router = APIRouter(tags=["appointments"])


def _get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=201,
    summary="Создать запись",
)
async def create_appointment(
    body: AppointmentCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> AppointmentResponse:
    """Сохранить заявку в БД и отправить уведомление в VK."""
    return await appointment_service.create_appointment(
        session,
        http_client,
        settings,
        body,
    )
