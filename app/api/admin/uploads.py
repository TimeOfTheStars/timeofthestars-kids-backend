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

# content-type → расширение, которое мы сохраняем
_ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
}


async def _save_image(file: UploadFile, *, subdir: str) -> str:
    """Сохранить картинку в static/<subdir>/, вернуть публичный URL вида /static/<subdir>/<name>."""
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Недопустимый тип файла. Разрешены: "
                + ", ".join(sorted(_ALLOWED_IMAGE_TYPES))
            ),
        )

    # Читаем чуть больше лимита, чтобы поймать превышение.
    contents = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком большой (макс {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пустой файл",
        )

    target_dir = _STATIC_ROOT / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    ext = _ALLOWED_IMAGE_TYPES[content_type]
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
