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
from app.schemas.news_post import NewsPostSyncResponse

logger = logging.getLogger(__name__)


_VK_WALL_RE = re.compile(r"wall(-?\d+)_(\d+)")

# Префиксы текста постов, которые НЕ нужно тащить в БД при автосинке.
_SKIP_PREFIXES: tuple[str, ...] = ("ПРЯМЫЕ ТРАНСЛЯЦИИ",)

# Сколько последних постов тянуть за один синк.
_NEWS_SYNC_LIMIT = 20


def _should_skip_by_text(text: str) -> bool:
    upper = text.lstrip().upper()
    return any(upper.startswith(prefix) for prefix in _SKIP_PREFIXES)


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


async def sync_news_from_vk(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> NewsPostSyncResponse:
    """Стянуть все посты со стены сообщества и добавить только новые.

    Уже сохранённые записи (по vk_owner_id + vk_post_id) не трогаем — чтобы
    ручные правки в админке не затирались. Посты, начинающиеся со слов из
    `_SKIP_PREFIXES` (например «ПРЯМЫЕ ТРАНСЛЯЦИИ»), пропускаются.
    """
    owner_id = -abs(settings.vk_reviews_group_id)  # для group walls owner_id отрицательный
    vk = VKClient(http_client, settings)
    posts = await vk.fetch_wall_posts(owner_id=owner_id, limit=_NEWS_SYNC_LIMIT)

    fetched = len(posts)
    skipped_empty = 0
    skipped_filtered = 0
    candidates: list[dict] = []

    for p in posts:
        text = p.get("text") or ""
        image = p.get("image")
        if _should_skip_by_text(text):
            skipped_filtered += 1
            continue
        if not text and not image:
            skipped_empty += 1
            continue
        candidates.append(p)

    candidate_ids = [int(p["post_id"]) for p in candidates]
    existing = await news_repo.existing_vk_post_ids(
        session,
        owner_id=owner_id,
        post_ids=candidate_ids,
    )

    new_rows: list[NewsPost] = []
    for p in candidates:
        pid = int(p["post_id"])
        if pid in existing:
            continue
        new_rows.append(
            NewsPost(
                vk_owner_id=owner_id,
                vk_post_id=pid,
                vk_post_date=p.get("date"),
                url=canonical_post_url(owner_id, pid),
                image=p.get("image"),
                excerpt=p.get("text") or "",
                position=0,
                is_visible=True,
            ),
        )

    created = await news_repo.bulk_create(session, new_rows)

    logger.info(
        "News sync done",
        extra={
            "fetched": fetched,
            "created_count": created,
            "skipped_existing": len(existing),
            "skipped_empty": skipped_empty,
            "skipped_filtered": skipped_filtered,
        },
    )

    return NewsPostSyncResponse(
        fetched=fetched,
        created=created,
        skipped_existing=len(existing),
        skipped_empty=skipped_empty,
        skipped_filtered=skipped_filtered,
    )


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
