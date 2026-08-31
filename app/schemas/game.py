"""Pydantic schemas: матчи, протокол матча и статистика.

Публичные схемы — camelCase, админские — snake_case (см. docs/public-api.md).
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.clock import ClockParseError, parse_clock

# ---------------------------------------------------------------- admin: матч


class GameTeamItem(BaseModel):
    """Команда в контексте матча."""

    id: uuid.UUID
    name: str
    city: str | None = None
    logo: str | None = None


class GameListItem(BaseModel):
    """Матч для админки. Собирается вручную в роуте."""

    id: uuid.UUID
    tournament_id: uuid.UUID
    position: int
    team_a: GameTeamItem
    team_b: GameTeamItem
    score_a: int | None
    score_b: int | None
    shots_a: int | None
    shots_b: int | None
    date: date_type
    time: time_type | None
    video_url: str | None
    scan: str | None
    is_finished: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("time")
    def _serialize_time(self, v: time_type | None) -> str | None:
        return v.strftime("%H:%M") if v else None


class GameCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    team_a_id: uuid.UUID
    team_b_id: uuid.UUID
    date: date_type
    time: time_type | None = None
    # «Табло матча»: голы и броски по командам.
    score_a: int | None = Field(default=None, ge=0, le=99)
    score_b: int | None = Field(default=None, ge=0, le=99)
    shots_a: int | None = Field(default=None, ge=0, le=999)
    shots_b: int | None = Field(default=None, ge=0, le=999)
    video_url: str | None = Field(default=None, max_length=1024)
    scan: str | None = Field(default=None, max_length=1024)
    # Не задан — сервис поставит следующий «МАТЧ №».
    position: int | None = Field(default=None, ge=0, le=10_000)

    @field_validator("video_url", "scan")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _teams_distinct(self) -> GameCreate:
        if self.team_a_id == self.team_b_id:
            msg = "Команда не может играть сама с собой"
            raise ValueError(msg)
        return self


class GameUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    team_a_id: uuid.UUID | None = None
    team_b_id: uuid.UUID | None = None
    date: date_type | None = None
    time: time_type | None = None
    score_a: int | None = Field(default=None, ge=0, le=99)
    score_b: int | None = Field(default=None, ge=0, le=99)
    shots_a: int | None = Field(default=None, ge=0, le=999)
    shots_b: int | None = Field(default=None, ge=0, le=999)
    video_url: str | None = Field(default=None, max_length=1024)
    scan: str | None = Field(default=None, max_length=1024)
    position: int | None = Field(default=None, ge=0, le=10_000)

    @field_validator("video_url", "scan")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


# ------------------------------------------------------------ admin: протокол


class PlayerStatLine(BaseModel):
    """Строка участия: этот игрок играл в этом матче за эту команду.

    Голы и передачи здесь принципиально не принимаются — они выводятся из событий.
    extra="forbid" гарантирует, что устаревший клиент, присылающий goals/assists,
    получит внятную 422, а не молча обнулит цифры.
    """

    model_config = ConfigDict(extra="forbid")

    player_id: uuid.UUID
    team_id: uuid.UUID
    is_goalie: bool = False
    # Минуты вратаря в матче. Заполняются, когда вратарей у команды двое и время
    # надо развести руками; иначе считаются по регламенту турнира.
    minutes_played: int | None = Field(default=None, ge=0, le=600)


class GameEventIn(BaseModel):
    """Гол из таблицы «ВЗЯТИЕ ВОРОТ»: период, время MM:SS, автор и до двух передач."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    team_id: uuid.UUID
    period: int = Field(..., ge=1, le=10)
    # На бланке время пишется как MM:SS внутри периода. Разбор — только в app/core/clock.py.
    time: str
    player_id: uuid.UUID
    assist1_player_id: uuid.UUID | None = None
    assist2_player_id: uuid.UUID | None = None

    @field_validator("time")
    @classmethod
    def _parseable_clock(cls, v: str) -> str:
        try:
            parse_clock(v)
        except ClockParseError as exc:
            raise ValueError(str(exc)) from exc
        return v

    @property
    def time_seconds(self) -> int:
        """Время внутри периода в секундах."""
        return parse_clock(self.time)

    @model_validator(mode="after")
    def _check_assists(self) -> GameEventIn:
        a1, a2 = self.assist1_player_id, self.assist2_player_id
        if a2 is not None and a1 is None:
            msg = "Вторая передача указана без первой"
            raise ValueError(msg)
        if a1 is not None and a1 == self.player_id:
            msg = "Автор гола не может быть ассистентом"
            raise ValueError(msg)
        if a2 is not None and a2 == self.player_id:
            msg = "Автор гола не может быть ассистентом"
            raise ValueError(msg)
        if a1 is not None and a2 is not None and a1 == a2:
            msg = "Передачи указаны на одного игрока дважды"
            raise ValueError(msg)
        return self

    @property
    def assist_ids(self) -> list[uuid.UUID]:
        return [a for a in (self.assist1_player_id, self.assist2_player_id) if a is not None]


class ProtocolRequest(BaseModel):
    """Полная замена протокола матча.

    events имеет три состояния (контракт унаследован из timeofthestars-backend-v2):
      * None (поле не передано) — таймлайн не трогаем, производные пересчитываем из БД;
      * []                      — таймлайн очищаем, голы/передачи обнуляем;
      * список                  — полная замена таймлайна.
    """

    model_config = ConfigDict(extra="forbid")

    score_a: int | None = Field(default=None, ge=0, le=99)
    score_b: int | None = Field(default=None, ge=0, le=99)
    shots_a: int | None = Field(default=None, ge=0, le=999)
    shots_b: int | None = Field(default=None, ge=0, le=999)
    stat_lines: list[PlayerStatLine] = Field(default_factory=list, max_length=200)
    events: list[GameEventIn] | None = Field(default=None, max_length=200)


class ProtocolStatLineOut(BaseModel):
    """Строка протокола на чтение: участие + производные + вычисленное вратарское."""

    player_id: uuid.UUID
    team_id: uuid.UUID
    full_name: str
    number: int | None
    position: str | None
    is_goalie: bool
    goals: int
    assists: int
    points: int
    # Только для вратарей и только когда вратарь у команды в матче один.
    goals_against: int | None = None
    saves: int | None = None
    # Вписанные минуты (если заполнены) либо расчёт по регламенту.
    minutes_played: int | None = None


class ProtocolEventOut(BaseModel):
    """Событие на чтение — ровно строка бланка «ВЗЯТИЕ ВОРОТ»."""

    id: uuid.UUID
    team_id: uuid.UUID
    period: int
    time: str
    time_seconds: int
    sort_order: int
    player_id: uuid.UUID
    player_name: str
    player_number: int | None
    assist1_player_id: uuid.UUID | None = None
    assist1_name: str | None = None
    assist1_number: int | None = None
    assist2_player_id: uuid.UUID | None = None
    assist2_name: str | None = None
    assist2_number: int | None = None


class ProtocolOut(BaseModel):
    """Матч + протокол для админки."""

    game: GameListItem
    period_minutes: int | None
    periods_count: int | None
    stat_lines: list[ProtocolStatLineOut]
    events: list[ProtocolEventOut]
    # Расхождение таймлайна со счётом: считается сервером, админка подсвечивает.
    goals_in_timeline_a: int
    goals_in_timeline_b: int
    # Вратарские не распределены (у команды 0 или 2+ вратарей) — админке нужно предупредить.
    goalie_ambiguous_team_ids: list[uuid.UUID] = Field(default_factory=list)


# ------------------------------------------------------------- public schemas


class TeamRef(BaseModel):
    """Команда для публичных ответов. `city` одинаков в snake_case и camelCase."""

    id: str
    name: str
    city: str | None = None
    logo: str | None = None


class PlayerRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    full_name: str = Field(serialization_alias="fullName")
    photo: str | None = None
    position: str | None = None
    birth_date: date_type | None = Field(default=None, serialization_alias="birthDate")


class StandingRowPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    place: int
    team: TeamRef
    games: int
    wins: int
    draws: int
    losses: int
    goals_for: int = Field(serialization_alias="goalsFor")
    goals_against: int = Field(serialization_alias="goalsAgainst")
    goal_diff: int = Field(serialization_alias="goalDiff")
    points: int


class GamePublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    match_no: int = Field(serialization_alias="matchNo")
    date: date_type
    time: time_type | None = None
    team_a: TeamRef = Field(serialization_alias="teamA")
    team_b: TeamRef = Field(serialization_alias="teamB")
    score_a: int | None = Field(default=None, serialization_alias="scoreA")
    score_b: int | None = Field(default=None, serialization_alias="scoreB")
    shots_a: int | None = Field(default=None, serialization_alias="shotsA")
    shots_b: int | None = Field(default=None, serialization_alias="shotsB")
    video_url: str | None = Field(default=None, serialization_alias="videoUrl")
    scan: str | None = None
    is_finished: bool = Field(serialization_alias="isFinished")

    @field_serializer("time")
    def _serialize_time(self, v: time_type | None) -> str | None:
        return v.strftime("%H:%M") if v else None


class GoalPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period: int
    time: str
    team_id: str = Field(serialization_alias="teamId")
    scorer: PlayerRef
    scorer_number: int | None = Field(default=None, serialization_alias="scorerNumber")
    assists: list[PlayerRef] = []
    assist_numbers: list[int | None] = Field(default_factory=list, serialization_alias="assistNumbers")


class PlayerStatsPublic(BaseModel):
    """Игрок турнира: заявка + статистика. Незаигравшие приходят с нулями."""

    model_config = ConfigDict(populate_by_name=True)

    player: PlayerRef
    team: TeamRef
    number: int | None = None
    games: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    is_goalie: bool = Field(default=False, serialization_alias="isGoalie")
    goals_against: int | None = Field(default=None, serialization_alias="goalsAgainst")
    saves: int | None = None
    minutes_played: int | None = Field(default=None, serialization_alias="minutesPlayed")


class GameProtocolPublic(BaseModel):
    """Матч с протоколом: составы обеих команд и хронология голов."""

    model_config = ConfigDict(populate_by_name=True)

    game: GamePublic
    roster_a: list[PlayerStatsPublic] = Field(serialization_alias="rosterA")
    roster_b: list[PlayerStatsPublic] = Field(serialization_alias="rosterB")
    goals: list[GoalPublic] = []


class StatTotalsPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    games: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    # Вратарские: null у полевых игроков и там, где табло не позволяет их распределить.
    goals_against: int | None = Field(default=None, serialization_alias="goalsAgainst")
    saves: int | None = None
    minutes_played: int | None = Field(default=None, serialization_alias="minutesPlayed")


class NamedTotalsPublic(BaseModel):
    """Разбивка карьеры: по турниру или по команде."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    totals: StatTotalsPublic


class PlayerCareerPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    player: PlayerRef
    career: StatTotalsPublic
    by_tournament: list[NamedTotalsPublic] = Field(serialization_alias="byTournament")
    by_team: list[NamedTotalsPublic] = Field(serialization_alias="byTeam")


class TeamCareerPublic(BaseModel):
    """Общая статистика команды за всю историю.

    Отдаются только ДЕЙСТВУЮЩИЕ значения: часть из них может быть вписана вручную
    и тогда не пересчитывается по матчам. Признак ручного ввода публично не
    раскрывается — он нужен только кабинету.
    """

    model_config = ConfigDict(populate_by_name=True)

    tournaments: int = 0
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = Field(default=0, serialization_alias="goalsFor")
    goals_against: int = Field(default=0, serialization_alias="goalsAgainst")
    goal_diff: int = Field(default=0, serialization_alias="goalDiff")
    points: int = 0


class TeamPublicCard(BaseModel):
    """Команда справочника + её общая статистика."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    city: str | None = None
    logo: str | None = None
    description: str | None = None
    stats: TeamCareerPublic
