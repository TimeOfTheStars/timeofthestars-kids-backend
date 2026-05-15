"""Фоновый автосинк отзывов и новостей из VK.

Запускается из lifespan, выключается чистой отменой задачи при shutdown.
Каждая итерация использует свою AsyncSession; ошибки одного синка не валят другой
и не убивают цикл — следующий тик пройдёт штатно.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.db.session import AsyncSessionLocal
from app.services import news_posts as news_service
from app.services import reviews as reviews_service

if TYPE_CHECKING:
    import httpx

    from app.core.config import Settings

logger = logging.getLogger(__name__)


async def _sync_reviews_once(settings: Settings, http_client: "httpx.AsyncClient") -> None:
    try:
        async with AsyncSessionLocal() as session:
            res = await reviews_service.sync_reviews_from_vk(session, http_client, settings)
        logger.info(
            "Auto-sync reviews ok",
            extra={
                "fetched": res.fetched,
                "created_count": res.created,
                "skipped_existing": res.skipped_existing,
                "skipped_empty": res.skipped_empty,
            },
        )
    except Exception:  # noqa: BLE001 — не валим цикл из-за одной ошибки
        logger.exception("Auto-sync reviews failed")


async def _sync_news_once(settings: Settings, http_client: "httpx.AsyncClient") -> None:
    try:
        async with AsyncSessionLocal() as session:
            res = await news_service.sync_news_from_vk(session, http_client, settings)
        logger.info(
            "Auto-sync news ok",
            extra={
                "fetched": res.fetched,
                "created_count": res.created,
                "skipped_existing": res.skipped_existing,
                "skipped_empty": res.skipped_empty,
                "skipped_filtered": res.skipped_filtered,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("Auto-sync news failed")


async def run_periodic_vk_sync(
    settings: Settings,
    http_client: "httpx.AsyncClient",
    *,
    interval_seconds: float,
    initial_delay_seconds: float,
) -> None:
    """Бесконечный цикл: спим initial_delay → синкаем оба источника → спим interval."""
    logger.info(
        "Background VK sync started",
        extra={
            "interval_seconds": interval_seconds,
            "initial_delay_seconds": initial_delay_seconds,
        },
    )
    try:
        if initial_delay_seconds > 0:
            await asyncio.sleep(initial_delay_seconds)
        while True:
            await _sync_reviews_once(settings, http_client)
            await _sync_news_once(settings, http_client)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Background VK sync cancelled")
        raise
