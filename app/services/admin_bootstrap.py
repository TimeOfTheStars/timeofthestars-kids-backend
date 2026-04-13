"""Создание первого администратора из env (если таблица пуста)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.roles import ROLE_ADMIN
from app.core.security import hash_password
from app.repositories import admin_users as admin_repo

logger = logging.getLogger(__name__)


async def bootstrap_first_admin_if_configured(session: AsyncSession, settings: Settings) -> None:
    if not settings.admin_bootstrap_username or not settings.admin_bootstrap_password:
        return
    if await admin_repo.count_admins(session) > 0:
        return
    username = settings.admin_bootstrap_username.strip()
    if await admin_repo.username_exists(session, username):
        return
    pwd_hash = hash_password(settings.admin_bootstrap_password)
    await admin_repo.create_admin(
        session,
        username=username,
        password_hash=pwd_hash,
        vk_user_id=settings.admin_bootstrap_vk_user_id,
        role=ROLE_ADMIN,
    )
    logger.warning(
        "Bootstrapped first admin user from ADMIN_BOOTSTRAP_* env; remove these variables in production",
        extra={"username": username},
    )
