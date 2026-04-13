"""Публичный API: вопрос с сайта."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.question import QuestionCreate, QuestionResponse
from app.services import questions as questions_service

router = APIRouter(tags=["questions"])


def _get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@router.post(
    "/questions",
    response_model=QuestionResponse,
    status_code=201,
    summary="Задать вопрос",
)
async def create_question(
    body: QuestionCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> QuestionResponse:
    """Сохранить ФИО и телефон и разослать уведомление в VK (как для заявок)."""
    return await questions_service.create_question(session, http_client, settings, body)
