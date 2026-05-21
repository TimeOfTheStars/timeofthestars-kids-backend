"""Pydantic schemas: Arenas (справочник площадок)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----- Admin (snake_case) -----


class ArenaListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str | None
    address: str | None
    city: str | None
    created_at: datetime
    updated_at: datetime


class ArenaCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=1024)
    address: str | None = Field(default=None, max_length=512)
    city: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("url", "address", "city")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ArenaUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=1024)
    address: str | None = Field(default=None, max_length=512)
    city: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("url", "address", "city")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None
