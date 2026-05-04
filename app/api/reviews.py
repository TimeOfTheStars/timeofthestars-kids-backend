"""Публичный HTTP API: отзывы для фронта."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories import reviews as reviews_repo
from app.schemas.review import ReviewPublic

router = APIRouter(tags=["reviews"])


@router.get(
    "/reviews",
    response_model=list[ReviewPublic],
    summary="Список отзывов для фронта",
)
async def list_reviews(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[ReviewPublic]:
    """Возвращает видимые отзывы в формате {text, author, pic}."""
    rows = await reviews_repo.list_visible(session, limit=limit)
    return [
        ReviewPublic(
            text=r.text,
            author=r.author_name,
            pic=r.author_photo_url,
        )
        for r in rows
    ]
