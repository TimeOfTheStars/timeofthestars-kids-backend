"""Личный кабинет: заявки и управление администраторами."""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.roles import ROLE_ADMIN
from app.core.security import hash_password
from app.db.session import get_db_session
from app.deps import get_current_admin, require_admin_role
from app.models.admin_user import AdminUser
from app.repositories import admin_users as admin_repo
from app.repositories import appointments as appointments_repo
from app.repositories import questions as questions_repo
from app.clients.vk_client import VKAPIError
from app.repositories import reviews as reviews_repo
from app.repositories import service_requests as service_requests_repo
from app.schemas.admin import (
    AdminCreateRequest,
    AdminListItem,
    AdminMeResponse,
    AdminUpdateRequest,
    AdminVkPatchRequest,
    AppointmentListItem,
)
from app.schemas.question import QuestionListItem
from app.schemas.review import (
    ReviewCreate,
    ReviewListItem,
    ReviewSyncResponse,
    ReviewUpdate,
)
from app.schemas.service_request import ServiceRequestListItem
from app.services import reviews as reviews_service

router = APIRouter()


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(admin: Annotated[AdminUser, Depends(get_current_admin)]) -> AdminMeResponse:
    return AdminMeResponse.model_validate(admin)


@router.patch("/me/vk", response_model=AdminMeResponse)
async def admin_patch_vk(
    body: AdminVkPatchRequest,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminMeResponse:
    user = await admin_repo.update_vk_user_id(session, admin.id, body.vk_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return AdminMeResponse.model_validate(user)


@router.get("/appointments", response_model=list[AppointmentListItem])
async def admin_list_appointments(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AppointmentListItem]:
    rows = await appointments_repo.list_appointments(session, skip=skip, limit=limit)
    return [AppointmentListItem.model_validate(r) for r in rows]


@router.get("/questions", response_model=list[QuestionListItem])
async def admin_list_questions(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[QuestionListItem]:
    rows = await questions_repo.list_questions(session, skip=skip, limit=limit)
    return [QuestionListItem.model_validate(r) for r in rows]


@router.get("/service-requests", response_model=list[ServiceRequestListItem])
async def admin_list_service_requests(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ServiceRequestListItem]:
    rows = await service_requests_repo.list_service_requests(session, skip=skip, limit=limit)
    return [ServiceRequestListItem.model_validate(r) for r in rows]


@router.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_appointment(
    appointment_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await appointments_repo.delete_appointment(session, appointment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_question(
    question_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await questions_repo.delete_question(session, question_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вопрос не найден")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/service-requests/{service_request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_service_request(
    service_request_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await service_requests_repo.delete_service_request(session, service_request_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка на услугу не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/requests/all")
async def admin_delete_all_requests(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    deleted_appointments = await appointments_repo.delete_all_appointments(session)
    deleted_service_requests = await service_requests_repo.delete_all_service_requests(session)
    deleted_questions = await questions_repo.delete_all_questions(session)
    return {
        "appointments": deleted_appointments,
        "service_requests": deleted_service_requests,
        "questions": deleted_questions,
    }


def _get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@router.get("/reviews", response_model=list[ReviewListItem])
async def admin_list_reviews(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[ReviewListItem]:
    rows = await reviews_repo.list_all(session, skip=skip, limit=limit)
    return [ReviewListItem.model_validate(r) for r in rows]


@router.post("/reviews", response_model=ReviewListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_review(
    body: ReviewCreate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewListItem:
    row = await reviews_repo.create_one(
        session,
        text=body.text,
        author_name=body.author_name,
        author_photo_url=body.author_photo_url,
        position=body.position,
        is_visible=body.is_visible,
    )
    return ReviewListItem.model_validate(row)


@router.patch("/reviews/{review_id}", response_model=ReviewListItem)
async def admin_update_review(
    review_id: uuid.UUID,
    body: ReviewUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewListItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
    row = await reviews_repo.update_one(session, review_id, raw)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отзыв не найден")
    return ReviewListItem.model_validate(row)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_review(
    review_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await reviews_repo.delete_one(session, review_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отзыв не найден")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reviews/sync", response_model=ReviewSyncResponse)
async def admin_sync_reviews(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> ReviewSyncResponse:
    """Стянуть новые комментарии из VK обсуждения. Существующие записи не трогаются."""
    try:
        return await reviews_service.sync_reviews_from_vk(session, http_client, settings)
    except VKAPIError as exc:
        if exc.error_code == 27:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "VK не разрешает board.getComments с group-токеном. "
                    "Задайте VK_READ_TOKEN: сервисный ключ приложения VK или user access token."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"VK API error {exc.error_code}: {exc.error_msg}",
        ) from exc


@router.get("/admins", response_model=list[AdminListItem])
async def admin_list_admins(
    _: Annotated[AdminUser, Depends(require_admin_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AdminListItem]:
    rows = await admin_repo.list_admins(session, skip=skip, limit=limit)
    return [AdminListItem.model_validate(r) for r in rows]


@router.post("/admins", response_model=AdminMeResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_admin(
    body: AdminCreateRequest,
    _: Annotated[AdminUser, Depends(require_admin_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminMeResponse:
    if await admin_repo.username_exists(session, body.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой логин уже занят")
    user = await admin_repo.create_admin(
        session,
        username=body.username,
        password_hash=hash_password(body.password),
        vk_user_id=body.vk_user_id,
        role=body.role,
    )
    return AdminMeResponse.model_validate(user)


@router.patch("/admins/{user_id}", response_model=AdminListItem)
async def admin_update_admin(
    user_id: uuid.UUID,
    body: AdminUpdateRequest,
    _: Annotated[AdminUser, Depends(require_admin_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminListItem:
    target = await admin_repo.get_by_id(session, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    raw = body.model_dump(exclude_unset=True)
    if "password" in raw:
        raw["password_hash"] = hash_password(raw.pop("password"))

    if "username" in raw:
        u = raw["username"].strip()
        if not u:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Логин не может быть пустым")
        raw["username"] = u
        if await admin_repo.username_exists(session, u, exclude_user_id=user_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой логин уже занят")

    was_admin_active = target.role == ROLE_ADMIN and target.is_active
    new_role = raw.get("role", target.role)
    new_active = raw.get("is_active", target.is_active)
    will_be_admin_active = new_role == ROLE_ADMIN and new_active
    if was_admin_active and not will_be_admin_active:
        cnt = await admin_repo.count_active_with_role(session, ROLE_ADMIN)
        if cnt <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя отключить или понизить последнего пользователя с ролью admin",
            )

    for key in ("username", "password_hash", "vk_user_id", "role", "is_active"):
        if key in raw:
            setattr(target, key, raw[key])

    await session.commit()
    await session.refresh(target)
    return AdminListItem.model_validate(target)
