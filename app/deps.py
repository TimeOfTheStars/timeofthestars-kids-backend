"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from jwt.exceptions import PyJWTError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.admin_user import AdminUser
from app.core.roles import ROLE_ADMIN
from app.repositories import admin_users as admin_repo

_bearer = HTTPBearer(auto_error=False)


async def get_current_admin(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AdminUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(settings=settings, token=creds.credentials)
        sub = payload.get("sub")
        if not sub:
            raise KeyError("sub")
        user_id = uuid.UUID(str(sub))
    except (PyJWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = await admin_repo.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")
    return user


async def require_admin_role(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminUser:
    """Только роль `admin`: управление пользователями и вкладка «Пользователи»."""
    if admin.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Раздел доступен только пользователям с ролью admin",
        )
    return admin
