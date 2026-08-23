"""Pydantic schemas: Players (справочник) и заявка на турнир.

Публичные схемы — camelCase, админские — snake_case (как в app/schemas/tournament.py).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.player import PLAYER_POSITIONS

# ----- Admin (snake_case) -----


class PlayerListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    birth_date: date | None
    position: str | None
    photo: str | None
    created_at: datetime
    updated_at: datetime


class PlayerCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(..., min_length=1, max_length=255)
    birth_date: date | None = None
    position: str | None = Field(default=None, max_length=32)
    photo: str | None = Field(default=None, max_length=1024)

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("position")
    @classmethod
    def _known_position(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if not v:
            return None
        if v not in PLAYER_POSITIONS:
            msg = f"Амплуа должно быть одним из: {', '.join(PLAYER_POSITIONS)}"
            raise ValueError(msg)
        return v

    @field_validator("photo")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class PlayerUpdate(PlayerCreate):
    """PATCH: те же правила, но все поля опциональны."""

    full_name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:  # type: ignore[override]
        if v is None:
            return None
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()


# ----- Admin: заявка на турнир -----


class RosterEntryItem(BaseModel):
    """Строка заявки: игрок в команде турнира под номером."""

    id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    player_id: uuid.UUID
    full_name: str
    birth_date: date | None
    position: str | None
    photo: str | None
    number: int | None


class RosterAddRequest(BaseModel):
    """Массовое добавление игроков в команду турнира."""

    model_config = ConfigDict(extra="forbid")

    team_id: uuid.UUID
    players: list[RosterAddEntry] = Field(default_factory=list, max_length=100)


class RosterAddEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: uuid.UUID
    number: int | None = Field(default=None, ge=1, le=99)


class RosterEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int | None = Field(default=None, ge=1, le=99)


RosterAddRequest.model_rebuild()
