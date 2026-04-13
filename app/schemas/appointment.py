"""Pydantic schemas for appointments."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    """Request body for POST /appointments."""

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

    @field_validator("phone", "parent_name", "child_name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()


class AppointmentResponse(BaseModel):
    """Successful API response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["created", "created_notify_failed"]
