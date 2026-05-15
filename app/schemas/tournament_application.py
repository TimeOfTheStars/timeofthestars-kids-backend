"""Pydantic-схемы для заявок на турнир."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----- Player -----


class TournamentPlayerApplicationCreate(BaseModel):
    """Тело POST /tournament-applications/player."""

    model_config = ConfigDict(str_strip_whitespace=True)

    parent_name: str = Field(..., min_length=1, max_length=255)
    child_name: str = Field(..., min_length=1, max_length=255)
    child_age: int = Field(..., ge=0, le=18)
    phone: str = Field(..., min_length=1, max_length=64)

    @field_validator("parent_name", "child_name", "phone")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()


class TournamentPlayerApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["created", "created_notify_failed"]


class TournamentPlayerApplicationListItem(BaseModel):
    """Элемент списка для админки."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_name: str
    child_name: str
    child_age: int
    phone: str
    created_at: datetime


# ----- Team -----


class TournamentTeamApplicationCreate(BaseModel):
    """Тело POST /tournament-applications/team."""

    model_config = ConfigDict(str_strip_whitespace=True)

    team_name: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=255)
    age_category: str = Field(..., min_length=1, max_length=32)
    coach_name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=1, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("team_name", "city", "age_category", "coach_name", "phone")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("comment")
    @classmethod
    def _comment_blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TournamentTeamApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["created", "created_notify_failed"]


class TournamentTeamApplicationListItem(BaseModel):
    """Элемент списка для админки."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_name: str
    city: str
    age_category: str
    coach_name: str
    phone: str
    comment: str | None
    created_at: datetime
