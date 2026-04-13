"""Схемы для вопросов с сайта."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuestionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(..., min_length=1, max_length=255, examples=["Иванова Мария Сергеевна"])
    phone: str = Field(..., min_length=1, max_length=64, examples=["+79991234567"])

    @field_validator("full_name", "phone")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()


class QuestionResponse(BaseModel):
    id: uuid.UUID
    status: Literal["created", "created_notify_failed"]


class QuestionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone: str
    created_at: datetime
