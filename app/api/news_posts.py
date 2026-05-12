"""Публичный HTTP API: новости для фронта."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.urls import absolutize
from app.db.session import get_db_session
from app.repositories import news_posts as news_repo
from app.schemas.news_post import NewsPostPublic

router = APIRouter(tags=["news"])


@router.get(
    "/news",
    response_model=list[NewsPostPublic],
    summary="Список новостей для фронта",
)
async def list_news(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[NewsPostPublic]:
    """Возвращает видимые новости в формате {image, excerpt, url}."""
    rows = await news_repo.list_visible(session, limit=limit)
    base = settings.public_base_url
    return [
        NewsPostPublic(image=absolutize(r.image, base), excerpt=r.excerpt, url=r.url)
        for r in rows
    ]
