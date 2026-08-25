"""Pydantic schemas: Teams и Tournaments.

Публичные схемы используют camelCase (см. tournaments-api.md).
Админские — snake_case.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.arena import ArenaListItem

# ----- Public (camelCase) -----


class TeamPublic(BaseModel):
    """{name, city, logo, photo} для фронта (в контексте турнира photo — общее фото состава)."""

    name: str
    city: str | None = None
    logo: str | None = None
    photo: str | None = None


class ArenaPublic(BaseModel):
    """Арена для фронта: name + ссылка на Яндекс.Карты + адрес/город."""

    name: str
    url: str | None = None
    address: str | None = None
    city: str | None = None


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
    end_time: time | None = Field(default=None, serialization_alias="endTime")
    arena: ArenaPublic
    season: str | None = None
    description: str | None = None
    url: str | None = None
    recordings_url: str | None = Field(default=None, serialization_alias="recordingsUrl")
    game_format: str | None = Field(default=None, serialization_alias="gameFormat")
    period_minutes: int | None = Field(default=None, serialization_alias="periodMinutes")
    periods_count: int | None = Field(default=None, serialization_alias="periodsCount")
    # Есть ли у турнира хотя бы один сыгранный матч — фронт по этому флагу решает,
    # показывать ли блок статистики, не делая лишний запрос.
    has_stats: bool = Field(default=False, serialization_alias="hasStats")
    teams: list[TeamPublic] = []

    @field_serializer("start_time", "end_time")
    def _serialize_time(self, v: time | None) -> str | None:
        return v.strftime("%H:%M") if v else None


# ----- Admin: Team -----


class TeamCareerAdmin(BaseModel):
    """Общая статистика команды за всю историю (админский вид)."""

    tournaments: int
    games: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_diff: int
    points: int


class TeamListItem(BaseModel):
    """Команда для админки. Собирается вручную в роуте — из-за расчётной статистики."""

    id: uuid.UUID
    name: str
    city: str | None
    logo: str | None
    description: str | None
    # Итог: расчёт по матчам плюс поправка.
    stats: TeamCareerAdmin
    # Только по заведённым матчам — чтобы в кабинете было видно, откуда взялся итог.
    computed: TeamCareerAdmin
    # Сохранённые поправки (итог − расчёт). Ноля и None здесь не бывает.
    corrections: dict[str, int]
    # Какие показатели имеют поправку. Итог по ним всё равно продолжает считаться.
    corrected_fields: list[str]
    created_at: datetime
    updated_at: datetime


class TeamStatTotals(BaseModel):
    """Желаемые ИТОГИ общей статистики команды. None — «поправки нет».

    Принимается итог, а хранится поправка (итог − расчёт по матчам), поэтому
    статистика продолжает считаться: новые матчи попадают в итог сами, а
    внесённая правка не устаревает.

    Очки не задаются: выводятся из итоговых побед и ничьих.
    """

    total_tournaments: int | None = Field(default=None, ge=0, le=10_000)
    total_games: int | None = Field(default=None, ge=0, le=100_000)
    total_wins: int | None = Field(default=None, ge=0, le=100_000)
    total_draws: int | None = Field(default=None, ge=0, le=100_000)
    total_losses: int | None = Field(default=None, ge=0, le=100_000)
    total_goals_for: int | None = Field(default=None, ge=0, le=1_000_000)
    total_goals_against: int | None = Field(default=None, ge=0, le=1_000_000)


class TeamCreate(TeamStatTotals):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    logo: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("city", "logo", "description")
    @classmethod
    def _logo_blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TeamUpdate(TeamStatTotals):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, max_length=255)
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

    @field_validator("city", "logo", "description")
    @classmethod
    def _logo_blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


# ----- Admin: Tournament -----


class TournamentTeamAdminItem(BaseModel):
    """Команда в составе конкретного турнира: данные команды + per-tournament photo."""

    id: uuid.UUID
    name: str
    city: str | None = None
    logo: str | None = None
    description: str | None = None
    photo: str | None = None


class TournamentTeamInput(BaseModel):
    """Элемент списка команд при создании/обновлении турнира."""

    model_config = ConfigDict(str_strip_whitespace=True)

    team_id: uuid.UUID
    photo: str | None = Field(default=None, max_length=1024)

    @field_validator("photo")
    @classmethod
    def _photo_blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TournamentListItem(BaseModel):
    """Полные данные турнира для админки (snake_case). Собирается вручную в роуте."""

    id: uuid.UUID
    title: str
    age_category: str
    birth_year: str | None
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None
    arena: ArenaListItem
    season: str | None
    description: str | None
    url: str | None
    recordings_url: str | None
    game_format: str | None
    period_minutes: int | None
    periods_count: int | None
    position: int
    is_visible: bool
    teams: list[TournamentTeamAdminItem]
    created_at: datetime
    updated_at: datetime

    @field_serializer("start_time", "end_time")
    def _serialize_time(self, v: time | None) -> str | None:
        return v.strftime("%H:%M") if v else None


class TournamentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=512)
    age_category: str = Field(..., min_length=1, max_length=32)
    birth_year: str | None = Field(default=None, max_length=32)
    start_date: date
    end_date: date
    start_time: time | None = None
    end_time: time | None = None
    arena_id: uuid.UUID
    season: str | None = Field(default=None, max_length=16)
    description: str | None = Field(default=None, max_length=4000)
    url: str | None = Field(default=None, max_length=1024)
    recordings_url: str | None = Field(default=None, max_length=1024)
    game_format: str | None = Field(default=None, max_length=16)
    period_minutes: int | None = Field(default=None, ge=1, le=120)
    periods_count: int | None = Field(default=None, ge=1, le=10)
    position: int = Field(default=0, ge=0, le=10_000)
    is_visible: bool = True
    teams: list[TournamentTeamInput] = Field(default_factory=list)

    @field_validator("title", "age_category")
    @classmethod
    def _required_not_blank(cls, v: str) -> str:
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("season", "description", "url", "recordings_url", "birth_year", "game_format")
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
    end_time: time | None = None
    arena_id: uuid.UUID | None = None
    season: str | None = Field(default=None, max_length=16)
    description: str | None = Field(default=None, max_length=4000)
    url: str | None = Field(default=None, max_length=1024)
    recordings_url: str | None = Field(default=None, max_length=1024)
    game_format: str | None = Field(default=None, max_length=16)
    period_minutes: int | None = Field(default=None, ge=1, le=120)
    periods_count: int | None = Field(default=None, ge=1, le=10)
    position: int | None = Field(default=None, ge=0, le=10_000)
    is_visible: bool | None = None
    teams: list[TournamentTeamInput] | None = None

    @field_validator("title", "age_category")
    @classmethod
    def _required_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            msg = "must not be blank"
            raise ValueError(msg)
        return v.strip()

    @field_validator("season", "description", "url", "recordings_url", "birth_year", "game_format")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None
