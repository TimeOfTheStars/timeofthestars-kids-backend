"""Admin user persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_user import AdminUser


async def count_admins(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(AdminUser)
    total = await session.scalar(stmt)
    return int(total or 0)


async def count_active_with_role(session: AsyncSession, role: str) -> int:
    stmt = select(func.count()).select_from(AdminUser).where(
        AdminUser.role == role,
        AdminUser.is_active.is_(True),
    )
    return int(await session.scalar(stmt) or 0)


async def get_by_username(session: AsyncSession, username: str) -> AdminUser | None:
    stmt = select(AdminUser).where(AdminUser.username == username)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> AdminUser | None:
    stmt = select(AdminUser).where(AdminUser.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_admin(
    session: AsyncSession,
    *,
    username: str,
    password_hash: str,
    vk_user_id: int | None = None,
    role: str,
) -> AdminUser:
    user = AdminUser(username=username, password_hash=password_hash, vk_user_id=vk_user_id, role=role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def list_vk_notify_user_ids(session: AsyncSession) -> list[int]:
    """Уникальные VK user_id активных админов, у которых поле задано (порядок — по дате создания)."""
    stmt = (
        select(AdminUser.vk_user_id)
        .where(AdminUser.is_active.is_(True), AdminUser.vk_user_id.isnot(None))
        .order_by(AdminUser.created_at.asc())
    )
    result = await session.execute(stmt)
    raw = [int(row[0]) for row in result.all() if row[0] is not None]
    seen: set[int] = set()
    out: list[int] = []
    for i in raw:
        if i > 0 and i not in seen:
            seen.add(i)
            out.append(i)
    return out


async def update_vk_user_id(
    session: AsyncSession,
    user_id: uuid.UUID,
    vk_user_id: int | None,
) -> AdminUser | None:
    user = await get_by_id(session, user_id)
    if user is None:
        return None
    user.vk_user_id = vk_user_id
    await session.commit()
    await session.refresh(user)
    return user


async def list_admins(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 200,
) -> list[AdminUser]:
    stmt = (
        select(AdminUser)
        .order_by(AdminUser.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def username_exists(
    session: AsyncSession,
    username: str,
    *,
    exclude_user_id: uuid.UUID | None = None,
) -> bool:
    stmt = select(func.count()).select_from(AdminUser).where(AdminUser.username == username)
    if exclude_user_id is not None:
        stmt = stmt.where(AdminUser.id != exclude_user_id)
    n = await session.scalar(stmt)
    return int(n or 0) > 0
