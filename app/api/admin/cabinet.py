"""Личный кабинет: заявки и управление администраторами."""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.roles import ROLE_ADMIN
from app.core.security import hash_password
from app.db.session import get_db_session
from app.deps import get_current_admin, require_admin_role
from app.models.admin_user import AdminUser
from app.clients.vk_client import VKAPIError
from app.repositories import admin_users as admin_repo
from app.repositories import appointments as appointments_repo
from app.repositories import arenas as arenas_repo
from app.repositories import news_posts as news_repo
from app.repositories import questions as questions_repo
from app.repositories import reviews as reviews_repo
from app.repositories import service_requests as service_requests_repo
from app.repositories import games as games_repo
from app.repositories import teams as teams_repo
from app.repositories import tournament_players as roster_repo
from app.repositories import tournament_applications as tournament_apps_repo
from app.repositories import tournaments as tournaments_repo
from app.schemas.admin import (
    AdminCreateRequest,
    AdminListItem,
    AdminMeResponse,
    AdminUpdateRequest,
    AdminVkPatchRequest,
    AppointmentListItem,
)
from app.schemas.arena import ArenaCreate, ArenaListItem, ArenaUpdate
from app.schemas.news_post import (
    NewsPostCreate,
    NewsPostListItem,
    NewsPostSyncResponse,
    NewsPostUpdate,
)
from app.schemas.question import QuestionListItem
from app.schemas.review import (
    ReviewCreate,
    ReviewListItem,
    ReviewSyncResponse,
    ReviewUpdate,
)
from app.schemas.service_request import ServiceRequestListItem
from app.schemas.tournament_application import (
    TournamentPlayerApplicationListItem,
    TournamentTeamApplicationListItem,
)
from app.schemas.tournament import (
    TeamCreate,
    TeamListItem,
    TeamUpdate,
    TournamentCreate,
    TournamentListItem,
    TournamentTeamAdminItem,
    TournamentTeamInput,
    TournamentUpdate,
)
from app.services import news_posts as news_service
from app.services import reviews as reviews_service
from app.services.news_posts import NewsPostError

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


@router.delete("/appointments")
async def admin_delete_all_appointments(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await appointments_repo.delete_all_appointments(session)}


@router.delete("/service-requests")
async def admin_delete_all_service_requests(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await service_requests_repo.delete_all_service_requests(session)}


@router.delete("/questions")
async def admin_delete_all_questions(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await questions_repo.delete_all_questions(session)}


@router.delete("/reviews")
async def admin_delete_all_reviews(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await reviews_repo.delete_all(session)}


@router.delete("/news")
async def admin_delete_all_news(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await news_repo.delete_all(session)}


@router.delete("/teams")
async def admin_delete_all_teams(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await teams_repo.delete_all(session)}


@router.get("/arenas", response_model=list[ArenaListItem])
async def admin_list_arenas(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[ArenaListItem]:
    rows = await arenas_repo.list_all(session, skip=skip, limit=limit)
    return [ArenaListItem.model_validate(r) for r in rows]


@router.post("/arenas", response_model=ArenaListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_arena(
    body: ArenaCreate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ArenaListItem:
    row = await arenas_repo.create_one(
        session,
        name=body.name,
        url=body.url,
        address=body.address,
        city=body.city,
    )
    return ArenaListItem.model_validate(row)


@router.patch("/arenas/{arena_id}", response_model=ArenaListItem)
async def admin_update_arena(
    arena_id: uuid.UUID,
    body: ArenaUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ArenaListItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
    row = await arenas_repo.update_one(session, arena_id, raw)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Арена не найдена")
    return ArenaListItem.model_validate(row)


@router.delete("/arenas/{arena_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_arena(
    arena_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    try:
        deleted = await arenas_repo.delete_one(session, arena_id)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Арена используется в одном или нескольких турнирах",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Арена не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/tournaments")
async def admin_delete_all_tournaments(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await tournaments_repo.delete_all(session)}


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
        raise _vk_error_to_http(exc) from exc


def _news_error_to_http(exc: NewsPostError) -> HTTPException:
    if exc.code == "duplicate":
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if exc.code == "not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _vk_error_to_http(exc: VKAPIError) -> HTTPException:
    if exc.error_code == 27:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "VK не разрешает чтение с group-токеном. "
                "Задайте VK_READ_TOKEN: сервисный ключ приложения VK или user access token."
            ),
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"VK API error {exc.error_code}: {exc.error_msg}",
    )


@router.get("/news", response_model=list[NewsPostListItem])
async def admin_list_news(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[NewsPostListItem]:
    rows = await news_repo.list_all(session, skip=skip, limit=limit)
    return [NewsPostListItem.model_validate(r) for r in rows]


@router.post("/news", response_model=NewsPostListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_news(
    body: NewsPostCreate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> NewsPostListItem:
    """Принимает URL поста VK, тянет текст и картинку, сохраняет."""
    try:
        row = await news_service.import_news_post_from_url(
            session,
            http_client,
            settings,
            url=body.url,
            position=body.position,
            is_visible=body.is_visible,
        )
    except NewsPostError as exc:
        raise _news_error_to_http(exc) from exc
    except VKAPIError as exc:
        raise _vk_error_to_http(exc) from exc
    return NewsPostListItem.model_validate(row)


@router.patch("/news/{news_id}", response_model=NewsPostListItem)
async def admin_update_news(
    news_id: uuid.UUID,
    body: NewsPostUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NewsPostListItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
    row = await news_repo.update_one(session, news_id, raw)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")
    return NewsPostListItem.model_validate(row)


@router.post("/news/{news_id}/refresh", response_model=NewsPostListItem)
async def admin_refresh_news(
    news_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> NewsPostListItem:
    """Перетянуть текст и картинку из VK, перезаписав текущие значения."""
    row = await news_repo.get_by_id(session, news_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")
    try:
        row = await news_service.refresh_news_post_from_vk(
            session,
            http_client,
            settings,
            row=row,
        )
    except NewsPostError as exc:
        raise _news_error_to_http(exc) from exc
    except VKAPIError as exc:
        raise _vk_error_to_http(exc) from exc
    return NewsPostListItem.model_validate(row)


@router.post("/news/sync", response_model=NewsPostSyncResponse)
async def admin_sync_news(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    http_client: Annotated[httpx.AsyncClient, Depends(_get_http_client)],
) -> NewsPostSyncResponse:
    """Стянуть все посты со стены группы и добавить только новые.

    Существующие записи не трогаются. Посты с префиксом «ПРЯМЫЕ ТРАНСЛЯЦИИ» пропускаются.
    """
    try:
        return await news_service.sync_news_from_vk(session, http_client, settings)
    except VKAPIError as exc:
        raise _vk_error_to_http(exc) from exc


@router.delete("/news/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_news(
    news_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await news_repo.delete_one(session, news_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Новость не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/teams", response_model=list[TeamListItem])
async def admin_list_teams(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[TeamListItem]:
    rows = await teams_repo.list_all(session, skip=skip, limit=limit)
    return [TeamListItem.model_validate(r) for r in rows]


@router.post("/teams", response_model=TeamListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_team(
    body: TeamCreate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TeamListItem:
    row = await teams_repo.create_one(
        session,
        name=body.name,
        logo=body.logo,
        description=body.description,
    )
    return TeamListItem.model_validate(row)


@router.patch("/teams/{team_id}", response_model=TeamListItem)
async def admin_update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TeamListItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
    row = await teams_repo.update_one(session, team_id, raw)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Команда не найдена")
    return TeamListItem.model_validate(row)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_team(
    team_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await teams_repo.delete_one(session, team_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Команда не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _validate_and_normalize_teams(
    session: AsyncSession,
    items: list[TournamentTeamInput],
) -> list[tuple[uuid.UUID, str | None]]:
    """Все ли team_id существуют. Удаляет дубли (оставляет первое вхождение). Сохраняет порядок и photo."""
    if not items:
        return []
    seen: set[uuid.UUID] = set()
    deduped: list[tuple[uuid.UUID, str | None]] = []
    for it in items:
        if it.team_id in seen:
            continue
        seen.add(it.team_id)
        deduped.append((it.team_id, it.photo))
    found = await teams_repo.get_by_ids(session, [tid for tid, _ in deduped])
    found_ids = {t.id for t in found}
    missing = [str(tid) for tid, _ in deduped if tid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не найдены команды: {', '.join(missing)}",
        )
    return deduped


async def _guard_removed_teams(
    session: AsyncSession,
    tournament_id: uuid.UUID,
    keep_team_ids: set[uuid.UUID],
) -> None:
    """Запретить убирать из турнира команду, у которой есть матчи или заявленные игроки.

    Без этой проверки удаление связи упало бы либо на RESTRICT от games (500),
    либо молча снесло бы заявку каскадом. Здесь — понятная 409.
    """
    existing = await tournaments_repo.get_by_id(session, tournament_id)
    if existing is None:
        return
    removed = {link.team_id for link in existing.team_links} - keep_team_ids
    if not removed:
        return

    blocked_by_games = removed & await games_repo.team_ids_with_games(session, tournament_id)
    blocked_by_roster = removed & await roster_repo.list_team_ids_with_players(
        session,
        tournament_id,
    )
    blocked = blocked_by_games | blocked_by_roster
    if not blocked:
        return

    names = {link.team_id: link.team.name for link in existing.team_links}
    listed = ", ".join(sorted(names.get(tid, str(tid)) for tid in blocked))
    reason = "матчи" if blocked_by_games else "заявленные игроки"
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Нельзя убрать из турнира команды, у которых есть {reason}: {listed}. "
            "Сначала удалите их матчи и состав."
        ),
    )


def _build_tournament_item(row) -> TournamentListItem:  # noqa: ANN001 — row: Tournament
    """Собрать админский ListItem руками: данные турнира + enriched-команды с per-tournament photo."""
    return TournamentListItem(
        id=row.id,
        title=row.title,
        age_category=row.age_category,
        birth_year=row.birth_year,
        start_date=row.start_date,
        end_date=row.end_date,
        start_time=row.start_time,
        end_time=row.end_time,
        arena=ArenaListItem.model_validate(row.arena),
        season=row.season,
        description=row.description,
        url=row.url,
        recordings_url=row.recordings_url,
        game_format=row.game_format,
        period_minutes=row.period_minutes,
        periods_count=row.periods_count,
        position=row.position,
        is_visible=row.is_visible,
        teams=[
            TournamentTeamAdminItem(
                id=link.team.id,
                name=link.team.name,
                logo=link.team.logo,
                description=link.team.description,
                photo=link.photo,
            )
            for link in row.team_links
        ],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/tournaments", response_model=list[TournamentListItem])
async def admin_list_tournaments(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[TournamentListItem]:
    rows = await tournaments_repo.list_all(session, skip=skip, limit=limit)
    return [_build_tournament_item(r) for r in rows]


@router.post(
    "/tournaments",
    response_model=TournamentListItem,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_tournament(
    body: TournamentCreate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TournamentListItem:
    if body.end_date < body.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date раньше start_date",
        )
    if await arenas_repo.get_by_id(session, body.arena_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Арена не найдена")
    teams = await _validate_and_normalize_teams(session, body.teams)
    fields = body.model_dump(exclude={"teams"})
    row = await tournaments_repo.create_one(session, fields=fields, teams=teams)
    return _build_tournament_item(row)


@router.patch("/tournaments/{tournament_id}", response_model=TournamentListItem)
async def admin_update_tournament(
    tournament_id: uuid.UUID,
    body: TournamentUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TournamentListItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
    teams_raw = raw.pop("teams", None)
    teams: list[tuple[uuid.UUID, str | None]] | None = None
    if teams_raw is not None:
        # body.teams был уже распарсен Pydantic'ом — повторно прогоним через схему,
        # чтобы получить список TournamentTeamInput и провалидировать (после exclude_unset
        # raw["teams"] это list[dict], а не list[модель]).
        items = [TournamentTeamInput.model_validate(t) for t in teams_raw]
        teams = await _validate_and_normalize_teams(session, items)
        await _guard_removed_teams(session, tournament_id, {tid for tid, _ in teams})
    if "arena_id" in raw and await arenas_repo.get_by_id(session, raw["arena_id"]) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Арена не найдена")
    # Проверка start_date/end_date с учётом текущих значений
    if "start_date" in raw or "end_date" in raw:
        existing = await tournaments_repo.get_by_id(session, tournament_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Турнир не найден")
        new_start = raw.get("start_date", existing.start_date)
        new_end = raw.get("end_date", existing.end_date)
        if new_end < new_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date раньше start_date",
            )
    row = await tournaments_repo.update_one(
        session,
        tournament_id,
        fields=raw,
        teams=teams,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Турнир не найден")
    return _build_tournament_item(row)


@router.delete("/tournaments/{tournament_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_tournament(
    tournament_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await tournaments_repo.delete_one(session, tournament_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Турнир не найден")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/tournament-applications/players",
    response_model=list[TournamentPlayerApplicationListItem],
)
async def admin_list_tournament_player_applications(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[TournamentPlayerApplicationListItem]:
    rows = await tournament_apps_repo.list_players(session, skip=skip, limit=limit)
    return [TournamentPlayerApplicationListItem.model_validate(r) for r in rows]


@router.delete(
    "/tournament-applications/players/{app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_tournament_player_application(
    app_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await tournament_apps_repo.delete_player(session, app_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/tournament-applications/players")
async def admin_delete_all_tournament_player_applications(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await tournament_apps_repo.delete_all_players(session)}


@router.get(
    "/tournament-applications/teams",
    response_model=list[TournamentTeamApplicationListItem],
)
async def admin_list_tournament_team_applications(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[TournamentTeamApplicationListItem]:
    rows = await tournament_apps_repo.list_teams(session, skip=skip, limit=limit)
    return [TournamentTeamApplicationListItem.model_validate(r) for r in rows]


@router.delete(
    "/tournament-applications/teams/{app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_tournament_team_application(
    app_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await tournament_apps_repo.delete_team(session, app_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/tournament-applications/teams")
async def admin_delete_all_tournament_team_applications(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    return {"deleted": await tournament_apps_repo.delete_all_teams(session)}


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
