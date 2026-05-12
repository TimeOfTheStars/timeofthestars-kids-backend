"""Утилиты для превращения относительных ссылок в абсолютные.

Используется в публичных API: если в БД сохранён локальный путь вида `/static/...`,
а в settings задан PUBLIC_BASE_URL — отдадим клиенту полный URL.
"""

from __future__ import annotations


def absolutize(url: str | None, base: str | None) -> str | None:
    """Локальный `/static/...` → `<base>/static/...`; абсолютные URL не трогаем."""
    if url is None:
        return None
    url = url.strip()
    if not url:
        return None
    lower = url.lower()
    if lower.startswith(("http://", "https://", "//", "data:")):
        return url
    if not base:
        return url
    if url.startswith("/"):
        return f"{base}{url}"
    return url
