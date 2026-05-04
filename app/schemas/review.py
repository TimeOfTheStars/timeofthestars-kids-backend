"""Pydantic schemas for reviews."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewPublic(BaseModel):
    """Формат, который ожидает фронт: text/author/pic."""

    text: str
    author: str
    pic: str | None = None


class ReviewListItem(BaseModel):
    """Элемент списка для админки."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vk_comment_id: int | None
    vk_topic_id: int | None
    text: str
    author_name: str
    author_photo_url: str | None
    position: int
    is_visible: bool
    created_at: datetime
    updated_at: datetime


class ReviewCreate(BaseModel):
    """Ручное создание отзыва из админки."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(..., min_length=1, max_length=8000)
    author_name: str = Field(..., min_length=1, max_length=255)
    author_photo_url: str | None = Field(default=None, max_length=1024)
    position: int = Field(default=0, ge=0, le=10_000)
    is_visible: bool = True

    @field_validator("text", "author_name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("author_photo_url")
    @classmethod
    def _photo_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ReviewUpdate(BaseModel):
    """Частичное обновление полей отзыва."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str | None = Field(default=None, min_length=1, max_length=8000)
    author_name: str | None = Field(default=None, min_length=1, max_length=255)
    author_photo_url: str | None = Field(default=None, max_length=1024)
    position: int | None = Field(default=None, ge=0, le=10_000)
    is_visible: bool | None = None

    @field_validator("text", "author_name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("author_photo_url")
    @classmethod
    def _photo_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ReviewSyncResponse(BaseModel):
    fetched: int = Field(..., description="Сколько комментариев получено из VK")
    created: int = Field(..., description="Сколько новых отзывов добавлено")
    skipped_existing: int = Field(..., description="Сколько уже было в БД (не трогали)")
    skipped_empty: int = Field(..., description="Сколько пропущено из-за пустого текста")
