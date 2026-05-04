"""Use-cases for news posts: импорт по URL и обновление из VK."""

from __future__ import annotations

import logging
import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vk_client import VKClient
from app.core.config import Settings
from app.models.news_post import NewsPost
from app.repositories import news_posts as news_repo

logger = logging.getLogger(__name__)


_VK_WALL_RE = re.compile(r"wall(-?\d+)_(\d+)")


class NewsPostError(Exception):
    """Ошибка импорта/обновления новости (валидация URL, отсутствие поста и т.п.)."""

    def __init__(self, message: str, *, code: str = "news_post_error") -> None:
        super().__init__(message)
        self.code = code


def parse_vk_post_url(url: str) -> tuple[int, int]:
    """Из URL вытащить (owner_id, post_id). Поддерживает /wall... и ?w=wall... формы."""
    if not url:
        raise NewsPostError("Пустая ссылка", code="invalid_url")
    m = _VK_WALL_RE.search(url)
    if not m:
        raise NewsPostError(
            "Ссылка не похожа на пост VK (ожидается …/wall<owner>_<post>)",
            code="invalid_url",
        )
    owner_id = int(m.group(1))
    post_id = int(m.group(2))
    if post_id <= 0 or owner_id == 0:
        raise NewsPostError("Некорректные id в ссылке", code="invalid_url")
    return owner_id, post_id


def canonical_post_url(owner_id: int, post_id: int) -> str:
    return f"https://vk.ru/wall{owner_id}_{post_id}"


async def _fetch_post_or_raise(
    http_client: httpx.AsyncClient,
    settings: Settings,
    *,
    owner_id: int,
    post_id: int,
) -> dict:
    vk = VKClient(http_client, settings)
    data = await vk.fetch_wall_post(owner_id=owner_id, post_id=post_id)
    if data is None:
        raise NewsPostError(
            "VK не вернул такой пост (возможно, удалён или скрыт настройками приватности).",
            code="not_found",
        )
    return data


async def import_news_post_from_url(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    *,
    url: str,
    position: int,
    is_visible: bool,
) -> NewsPost:
    owner_id, post_id = parse_vk_post_url(url)

    existing = await news_repo.get_by_vk_ref(session, owner_id=owner_id, post_id=post_id)
    if existing is not None:
        raise NewsPostError("Этот пост уже добавлен.", code="duplicate")

    data = await _fetch_post_or_raise(
        http_client,
        settings,
        owner_id=owner_id,
        post_id=post_id,
    )
    excerpt = (data.get("text") or "").strip()
    image = data.get("image")

    row = await news_repo.create_one(
        session,
        vk_owner_id=owner_id,
        vk_post_id=post_id,
        url=canonical_post_url(owner_id, post_id),
        image=image,
        excerpt=excerpt,
        position=position,
        is_visible=is_visible,
    )
    logger.info(
        "News post imported",
        extra={
            "news_post_id": str(row.id),
            "vk_owner_id": owner_id,
            "vk_post_id": post_id,
            "has_image": bool(image),
            "excerpt_len": len(excerpt),
        },
    )
    return row


async def refresh_news_post_from_vk(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    *,
    row: NewsPost,
) -> NewsPost:
    """Перетянуть текст и картинку из VK поверх текущей записи."""
    data = await _fetch_post_or_raise(
        http_client,
        settings,
        owner_id=row.vk_owner_id,
        post_id=row.vk_post_id,
    )
    row.excerpt = (data.get("text") or "").strip()
    row.image = data.get("image")
    await session.commit()
    await session.refresh(row)
    return row
