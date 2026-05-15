"""Pydantic schemas: Teams и Tournaments.

Публичные схемы используют camelCase (см. tournaments-api.md).
Админские — snake_case.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


# ----- Public (camelCase) -----


class TeamPublic(BaseModel):
    """{name, logo} для фронта."""

    name: str
    logo: str | None = None


class TournamentPublic(BaseModel):
    """Формат для GET /tournaments — camelCase согласно tournaments-api.md."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    age_category: str = Field(serialization_alias="ageCategory")
    birth_year: str | None = Field(default=None, serialization_alias="birthYear")
    start_date: date = Field(serialization_alias="startDate")
    end_date: date = Field(serialization_alias="endDate")
    start_time: time | None = Field(default=None, serialization_alias="startTime")
    location: str
    city: str | None = None
    season: str | None = None
    description: str | None = None
    url: str | None = None
    recordings_url: str | None = Field(default=None, serialization_alias="recordingsUrl")
    teams: list[TeamPublic] = []

    @field_serializer("start_time")
    def _serialize_start_time(self, v: time | None) -> str | None:
        return v.strftime("%H:%M") if v else None


# ----- Admin: Team -----


class TeamListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    logo: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class TeamCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    logo: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("logo", "description")
    @classmethod
    def _logo_blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TeamUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    logo: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("logo", "description")
    @classmethod
    def _logo_blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


# ----- Admin: Tournament -----


class TournamentListItem(BaseModel):
    """Полные данные турнира для админки (snake_case)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    age_category: str
    birth_year: str | None
    start_date: date
    end_date: date
    start_time: time | None
    location: str
    city: str | None
    season: str | None
    description: str | None
    url: str | None
    recordings_url: str | None
    position: int
    is_visible: bool
    teams: list[TeamListItem]

    @field_serializer("start_time")
    def _serialize_start_time(self, v: time | None) -> str | None:
        return v.strftime("%H:%M") if v else None
    created_at: datetime
    updated_at: datetime


class TournamentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=512)
    age_category: str = Field(..., min_length=1, max_length=32)
    birth_year: str | None = Field(default=None, max_length=32)
    start_date: date
    end_date: date
    start_time: time | None = None
    location: str = Field(..., min_length=1, max_length=512)
    city: str | None = Field(default=None, max_length=255)
    season: str | None = Field(default=None, max_length=16)
    description: str | None = Field(default=None, max_length=4000)
    url: str | None = Field(default=None, max_length=1024)
    recordings_url: str | None = Field(default=None, max_length=1024)
    position: int = Field(default=0, ge=0, le=10_000)
    is_visible: bool = True
    team_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("title", "age_category", "location")
    @classmethod
    def _required_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("city", "season", "description", "url", "recordings_url", "birth_year")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TournamentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=512)
    age_category: str | None = Field(default=None, min_length=1, max_length=32)
    birth_year: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    location: str | None = Field(default=None, min_length=1, max_length=512)
    city: str | None = Field(default=None, max_length=255)
    season: str | None = Field(default=None, max_length=16)
    description: str | None = Field(default=None, max_length=4000)
    url: str | None = Field(default=None, max_length=1024)
    recordings_url: str | None = Field(default=None, max_length=1024)
    position: int | None = Field(default=None, ge=0, le=10_000)
    is_visible: bool | None = None
    team_ids: list[uuid.UUID] | None = None

    @field_validator("title", "age_category", "location")
    @classmethod
    def _required_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("city", "season", "description", "url", "recordings_url", "birth_year")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None
