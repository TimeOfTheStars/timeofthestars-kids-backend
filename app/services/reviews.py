"""Use-cases for reviews (синхронизация из VK обсуждения)."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vk_client import VKClient
from app.core.config import Settings
from app.models.review import Review
from app.repositories import reviews as reviews_repo
from app.schemas.review import ReviewSyncResponse

logger = logging.getLogger(__name__)


async def sync_reviews_from_vk(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> ReviewSyncResponse:
    """Стянуть комментарии из обсуждения VK и добавить только новые.

    Существующие записи (по vk_comment_id) не трогаем — чтобы ручные правки
    в админке не затирались при повторной синхронизации.
    """
    vk = VKClient(http_client, settings)
    comments = await vk.fetch_topic_comments(
        group_id=settings.vk_reviews_group_id,
        topic_id=settings.vk_reviews_topic_id,
    )

    fetched = len(comments)
    skipped_empty = 0

    candidates: list[dict] = []
    for c in comments:
        if not c.get("text"):
            skipped_empty += 1
            continue
        candidates.append(c)

    candidate_ids = [int(c["comment_id"]) for c in candidates]
    existing = await reviews_repo.existing_vk_comment_ids(session, candidate_ids)

    new_rows: list[Review] = []
    for idx, c in enumerate(candidates):
        cid = int(c["comment_id"])
        if cid in existing:
            continue
        new_rows.append(
            Review(
                vk_comment_id=cid,
                vk_topic_id=settings.vk_reviews_topic_id,
                text=c["text"],
                author_name=c["author_name"],
                author_photo_url=c.get("author_photo_url"),
                position=idx,
                is_visible=True,
            ),
        )

    created = await reviews_repo.bulk_create(session, new_rows)

    logger.info(
        "Reviews sync done",
        extra={
            "fetched": fetched,
            "created_count": created,
            "skipped_existing": len(existing),
            "skipped_empty": skipped_empty,
        },
    )

    return ReviewSyncResponse(
        fetched=fetched,
        created=created,
        skipped_existing=len(existing),
        skipped_empty=skipped_empty,
    )
