"""Авторизация администратора (JWT)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db_session
from app.repositories import admin_users as admin_repo
from app.schemas.admin import AdminLoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def admin_login(
    body: AdminLoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = await admin_repo.get_by_username(session, body.username.strip())
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь отключён")
    token = create_access_token(
        settings=settings,
        subject_user_id=user.id,
        username=user.username,
        role=user.role,
    )
    return TokenResponse(access_token=token)
