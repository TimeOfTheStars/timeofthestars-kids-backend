"""Persistence for news posts."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_post import NewsPost


def _news_order():
    """Админская «position» имеет приоритет; внутри — по дате поста в VK, новейшие сверху."""
    return (
        NewsPost.position.asc(),
        NewsPost.vk_post_date.desc().nulls_last(),
        NewsPost.created_at.desc(),
    )


async def list_visible(session: AsyncSession, *, limit: int = 200) -> list[NewsPost]:
    stmt = (
        select(NewsPost)
        .where(NewsPost.is_visible.is_(True))
        .order_by(*_news_order())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_all(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 200,
) -> list[NewsPost]:
    stmt = (
        select(NewsPost)
        .order_by(*_news_order())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, news_id: uuid.UUID) -> NewsPost | None:
    stmt = select(NewsPost).where(NewsPost.id == news_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_vk_ref(
    session: AsyncSession,
    *,
    owner_id: int,
    post_id: int,
) -> NewsPost | None:
    stmt = select(NewsPost).where(
        NewsPost.vk_owner_id == owner_id,
        NewsPost.vk_post_id == post_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def existing_vk_post_ids(
    session: AsyncSession,
    *,
    owner_id: int,
    post_ids: list[int],
) -> set[int]:
    if not post_ids:
        return set()
    stmt = select(NewsPost.vk_post_id).where(
        NewsPost.vk_owner_id == owner_id,
        NewsPost.vk_post_id.in_(post_ids),
    )
    result = await session.execute(stmt)
    return {int(r[0]) for r in result.all() if r[0] is not None}


async def bulk_create(session: AsyncSession, rows: list[NewsPost]) -> int:
    if not rows:
        return 0
    session.add_all(rows)
    await session.commit()
    return len(rows)


async def create_one(
    session: AsyncSession,
    *,
    vk_owner_id: int,
    vk_post_id: int,
    url: str,
    image: str | None,
    excerpt: str,
    position: int = 0,
    is_visible: bool = True,
) -> NewsPost:
    row = NewsPost(
        vk_owner_id=vk_owner_id,
        vk_post_id=vk_post_id,
        url=url,
        image=image,
        excerpt=excerpt,
        position=position,
        is_visible=is_visible,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_one(
    session: AsyncSession,
    news_id: uuid.UUID,
    fields: dict[str, Any],
) -> NewsPost | None:
    row = await get_by_id(session, news_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_one(session: AsyncSession, news_id: uuid.UUID) -> bool:
    stmt = delete(NewsPost).where(NewsPost.id == news_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all(session: AsyncSession) -> int:
    result = await session.execute(delete(NewsPost))
    await session.commit()
    return int(result.rowcount or 0)
