"""Загрузка файлов из админки (логотипы команд и т.п.)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.deps import get_current_admin
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"])

# project_root/static/teams
_STATIC_ROOT = Path(__file__).resolve().parents[3] / "static"

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
# Скан бумажного протокола — это фото с телефона или PDF, 5 МБ им мало.
_MAX_SCAN_BYTES = 10 * 1024 * 1024  # 10 MB

# content-type → расширение, которое мы сохраняем
_ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
}


# Скан протокола может быть и PDF, а не только фотографией.
_ALLOWED_SCAN_TYPES: dict[str, str] = {**_ALLOWED_IMAGE_TYPES, "application/pdf": ".pdf"}


async def _save_image(
    file: UploadFile,
    *,
    subdir: str,
    allowed: dict[str, str] | None = None,
    max_bytes: int | None = None,
) -> str:
    """Сохранить файл в static/<subdir>/, вернуть публичный URL вида /static/<subdir>/<name>."""
    allowed = allowed or _ALLOWED_IMAGE_TYPES
    max_bytes = max_bytes or _MAX_UPLOAD_BYTES
    content_type = (file.content_type or "").lower()
    if content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Недопустимый тип файла. Разрешены: " + ", ".join(sorted(allowed))),
        )

    # Читаем чуть больше лимита, чтобы поймать превышение.
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком большой (макс {max_bytes // (1024 * 1024)} MB)",
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пустой файл",
        )

    target_dir = _STATIC_ROOT / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    ext = allowed[content_type]
    name = f"{uuid.uuid4().hex}{ext}"
    (target_dir / name).write_bytes(contents)

    public_url = f"/static/{subdir}/{name}"
    logger.info(
        "Image uploaded",
        extra={"subdir": subdir, "bytes": len(contents), "url": public_url},
    )
    return public_url


@router.post("/uploads/team-logo")
async def upload_team_logo(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    file: Annotated[UploadFile, File(...)],
) -> dict[str, str]:
    """Загрузить логотип команды. Возвращает {url}."""
    url = await _save_image(file, subdir="teams")
    return {"url": url}


@router.post("/uploads/team-photo")
async def upload_team_photo(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    file: Annotated[UploadFile, File(...)],
) -> dict[str, str]:
    """Загрузить общую фотографию состава команды на конкретном турнире."""
    url = await _save_image(file, subdir="team-photos")
    return {"url": url}


@router.post("/uploads/player-photo")
async def upload_player_photo(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    file: Annotated[UploadFile, File(...)],
) -> dict[str, str]:
    """Загрузить фотографию игрока. Возвращает {url}."""
    url = await _save_image(file, subdir="player-photos")
    return {"url": url}


@router.post("/uploads/game-scan")
async def upload_game_scan(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    file: Annotated[UploadFile, File(...)],
) -> dict[str, str]:
    """Загрузить скан бумажного протокола матча — картинкой или PDF."""
    url = await _save_image(
        file,
        subdir="protocols",
        allowed=_ALLOWED_SCAN_TYPES,
        max_bytes=_MAX_SCAN_BYTES,
    )
    return {"url": url}
