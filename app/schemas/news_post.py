"""Pydantic schemas for news posts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NewsPostPublic(BaseModel):
    """Формат для фронта: {image, excerpt, url}."""

    image: str | None = None
    excerpt: str
    url: str


class NewsPostListItem(BaseModel):
    """Полные данные для админки."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vk_owner_id: int
    vk_post_id: int
    url: str
    image: str | None
    excerpt: str
    position: int
    is_visible: bool
    created_at: datetime
    updated_at: datetime


class NewsPostCreate(BaseModel):
    """Создание из админки: вставляем только URL поста VK."""

    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(..., min_length=1, max_length=512)
    position: int = Field(default=0, ge=0, le=10_000)
    is_visible: bool = True

    @field_validator("url")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()


class NewsPostUpdate(BaseModel):
    """Частичное обновление полей новости."""

    model_config = ConfigDict(str_strip_whitespace=True)

    excerpt: str | None = Field(default=None, max_length=20_000)
    image: str | None = Field(default=None, max_length=1024)
    url: str | None = Field(default=None, min_length=1, max_length=512)
    position: int | None = Field(default=None, ge=0, le=10_000)
    is_visible: bool | None = None

    @field_validator("excerpt", "url")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("image")
    @classmethod
    def _image_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None
