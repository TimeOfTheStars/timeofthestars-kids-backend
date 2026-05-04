"""Persistence for reviews."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review


async def list_visible(session: AsyncSession, *, limit: int = 200) -> list[Review]:
    stmt = (
        select(Review)
        .where(Review.is_visible.is_(True))
        .order_by(Review.position.asc(), Review.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_all(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 200,
) -> list[Review]:
    stmt = (
        select(Review)
        .order_by(Review.position.asc(), Review.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, review_id: uuid.UUID) -> Review | None:
    stmt = select(Review).where(Review.id == review_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def existing_vk_comment_ids(
    session: AsyncSession,
    vk_comment_ids: list[int],
) -> set[int]:
    if not vk_comment_ids:
        return set()
    stmt = select(Review.vk_comment_id).where(Review.vk_comment_id.in_(vk_comment_ids))
    result = await session.execute(stmt)
    return {int(r[0]) for r in result.all() if r[0] is not None}


async def bulk_create(session: AsyncSession, rows: list[Review]) -> int:
    if not rows:
        return 0
    session.add_all(rows)
    await session.commit()
    return len(rows)


async def create_one(
    session: AsyncSession,
    *,
    text: str,
    author_name: str,
    author_photo_url: str | None,
    position: int = 0,
    is_visible: bool = True,
) -> Review:
    row = Review(
        text=text,
        author_name=author_name,
        author_photo_url=author_photo_url,
        position=position,
        is_visible=is_visible,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_one(
    session: AsyncSession,
    review_id: uuid.UUID,
    fields: dict[str, Any],
) -> Review | None:
    row = await get_by_id(session, review_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_one(session: AsyncSession, review_id: uuid.UUID) -> bool:
    stmt = delete(Review).where(Review.id == review_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)
