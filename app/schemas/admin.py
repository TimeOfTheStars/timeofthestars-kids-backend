"""Pydantic schemas for admin API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: str
    vk_user_id: int | None = None


class AppointmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    parent_name: str
    child_name: str
    child_age: int
    created_at: datetime


class AdminCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=256)
    vk_user_id: int | None = Field(
        default=None,
        description="VK user_id для уведомлений; можно задать позже в кабинете",
    )
    role: Literal["admin", "viewer"] = "viewer"

    @field_validator("username")
    @classmethod
    def _username_normalized(cls, v: str) -> str:
        u = v.strip()
        if not u:
            msg = "username must not be blank"
            raise ValueError(msg)
        return u

    @field_validator("vk_user_id")
    @classmethod
    def _vk_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            msg = "vk_user_id must be positive"
            raise ValueError(msg)
        return v


class AdminListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: str
    vk_user_id: int | None = None
    is_active: bool
    created_at: datetime


class AdminUpdateRequest(BaseModel):
    """Частичное обновление пользователя (только переданные поля)."""

    username: str | None = Field(default=None, min_length=3, max_length=64)
    password: str | None = Field(default=None, min_length=8, max_length=256)
    vk_user_id: int | None = None
    role: Literal["admin", "viewer"] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            msg = "Укажите хотя бы одно поле"
            raise ValueError(msg)
        return self

    @field_validator("username")
    @classmethod
    def _username_if_set(cls, v: str | None) -> str | None:
        if v is None:
            return v
        u = v.strip()
        if not u:
            msg = "username must not be blank"
            raise ValueError(msg)
        return u

    @field_validator("vk_user_id")
    @classmethod
    def _vk_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            msg = "vk_user_id must be positive"
            raise ValueError(msg)
        return v


class AdminVkPatchRequest(BaseModel):
    """Обновить свой VK user_id для рассылки уведомлений; явно передайте null чтобы отвязать."""

    vk_user_id: int | None = Field(
        ...,
        description="Положительный VK user_id или null чтобы убрать привязку",
    )

    @field_validator("vk_user_id")
    @classmethod
    def _vk_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            msg = "vk_user_id must be positive"
            raise ValueError(msg)
        return v
