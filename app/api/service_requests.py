"""HTTP API: заявки на услуги."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.service_request import ServiceRequestCreate, ServiceRequestResponse
from app.services import service_requests as service_requests_service

router = APIRouter(tags=["service-requests"])


def _get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@router.post(
    "/service-requests",
    response_model=ServiceRequestResponse,
    status_code=201,
    summary="Создать заявку на услугу",
)
async def create_service_request(
    body: ServiceRequestCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> ServiceRequestResponse:
    """Сохранить заявку (как на запись) + услуга; уведомление в VK тем же списком получателей."""
    return await service_requests_service.create_service_request(
        session,
        http_client,
        settings,
        body,
    )
