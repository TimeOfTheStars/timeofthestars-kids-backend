"""Pydantic schemas for service requests (заявки на услуги)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceRequestCreate(BaseModel):
    """Тело POST /service-requests — как заявка + услуга с фронта."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: str = Field(..., min_length=1, max_length=64, examples=["+79991234567"])
    parent_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ФИО родителя",
        examples=["Иванова Мария Сергеевна"],
    )
    child_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ФИО ребёнка",
        examples=["Иванов Пётр Иванович"],
    )
    child_age: int = Field(..., ge=0, le=18, examples=[7])
    service: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Название или код услуги с фронта",
        examples=["Диагностика речи"],
    )

    @field_validator("phone", "parent_name", "child_name", "service")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()


class ServiceRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["created", "created_notify_failed"]


class ServiceRequestListItem(BaseModel):
    """Элемент списка для кабинета."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    parent_name: str
    child_name: str
    child_age: int
    service: str
    created_at: datetime
