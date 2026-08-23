"""Публичный HTTP API статистики: таблица, матчи, игроки турнира, карточка игрока."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import format_clock
from app.core.config import Settings, get_settings
from app.core.urls import absolutize
from app.db.session import get_db_session
from app.models.game import Game
from app.models.tournament import Tournament
from app.repositories import games as games_repo
from app.repositories import tournaments as tournaments_repo
from app.schemas.game import (
    GameProtocolPublic,
    GamePublic,
    GoalPublic,
    NamedTotalsPublic,
    PlayerCareerPublic,
    PlayerRef,
    PlayerStatsPublic,
    StandingRowPublic,
    StatTotalsPublic,
    TeamRef,
)
from app.services import stats as stats_service

router = APIRouter(tags=["stats"])

_CACHE_CONTROL = "public, max-age=300"


async def _require_visible_tournament(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> Tournament:
    row = await tournaments_repo.get_by_id(session, tournament_id)
    if row is None or not row.is_visible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Турнир не найден")
    return row


def _team_ref(team_id: uuid.UUID, name: str, logo: str | None, base: str | None) -> TeamRef:
    return TeamRef(id=str(team_id), name=name, logo=absolutize(logo, base))


def _player_ref(player, base: str | None) -> PlayerRef:  # noqa: ANN001 — player: Player
    return PlayerRef(
        id=str(player.id),
        full_name=player.full_name,
        photo=absolutize(player.photo, base),
        position=player.position,
        birth_date=player.birth_date,
    )


# ------------------------------------------------------------------ таблица


@router.get(
    "/tournaments/{tournament_id}/standings",
    response_model=list[StandingRowPublic],
    summary="Таблица турнира",
)
async def tournament_standings(
    tournament_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> list[StandingRowPublic]:
    """Место, И, В/Н/П, забито/пропущено, разница, очки. Сервер отдаёт отсортированным."""
    await _require_visible_tournament(session, tournament_id)
    response.headers["Cache-Control"] = _CACHE_CONTROL
    base = settings.public_base_url
    rows = await stats_service.compute_standings(session, tournament_id)
    return [
        StandingRowPublic(
            place=idx,
            team=_team_ref(core.team_id, core.name, logo, base),
            games=core.games,
            wins=core.wins,
            draws=core.draws,
            losses=core.losses,
            goals_for=core.goals_for,
            goals_against=core.goals_against,
            goal_diff=core.goal_diff,
            points=core.points,
        )
        for idx, (core, logo) in enumerate(rows, start=1)
    ]


# -------------------------------------------------------------------- матчи


def _game_public(game: Game, base: str | None) -> GamePublic:
    return GamePublic(
        id=str(game.id),
        match_no=game.position,
        date=game.date,
        time=game.time,
        team_a=_team_ref(game.team_a.id, game.team_a.name, game.team_a.logo, base),
        team_b=_team_ref(game.team_b.id, game.team_b.name, game.team_b.logo, base),
        score_a=game.score_a,
        score_b=game.score_b,
        shots_a=game.shots_a,
        shots_b=game.shots_b,
        video_url=game.video_url,
        scan=absolutize(game.scan, base),
        is_finished=game.is_finished,
    )


@router.get(
    "/tournaments/{tournament_id}/games",
    response_model=list[GamePublic],
    summary="Матчи турнира",
)
async def tournament_games(
    tournament_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> list[GamePublic]:
    """Календарь и результаты. Стадий нет — плоский список в порядке «МАТЧ №»."""
    await _require_visible_tournament(session, tournament_id)
    response.headers["Cache-Control"] = _CACHE_CONTROL
    base = settings.public_base_url
    games = await games_repo.list_for_tournament(session, tournament_id)
    return [_game_public(g, base) for g in games]


@router.get(
    "/games/{game_id}",
    response_model=GameProtocolPublic,
    summary="Матч с протоколом: составы и хронология голов",
)
async def game_protocol(
    game_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> GameProtocolPublic:
    game = await games_repo.get_by_id(session, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Матч не найден")
    await _require_visible_tournament(session, game.tournament_id)
    response.headers["Cache-Control"] = _CACHE_CONTROL
    base = settings.public_base_url

    rows = await stats_service.tournament_players_with_stats(session, game.tournament_id)
    by_player = {r.entry.player_id: r for r in rows}
    played = {line.player_id for line in game.stat_lines}

    # Вратарские показатели ЭТОГО матча выводятся из табло — ровно как на бланке.
    # Распределяем только когда у команды в матче единственный вратарь.
    goalies_by_team: dict[uuid.UUID, list[uuid.UUID]] = {}
    for line in game.stat_lines:
        if line.is_goalie:
            goalies_by_team.setdefault(line.team_id, []).append(line.player_id)

    goalie_values: dict[uuid.UUID, tuple[int | None, int | None]] = {}
    if game.score_a is not None and game.score_b is not None:
        score = stats_service.GameScore(
            team_a_id=game.team_a_id,
            team_b_id=game.team_b_id,
            score_a=game.score_a,
            score_b=game.score_b,
            shots_a=game.shots_a,
            shots_b=game.shots_b,
        )
        for tid, ids in goalies_by_team.items():
            if len(ids) == 1:
                goalie_values[ids[0]] = stats_service.goalie_totals_for_game(score, tid)

    tournament = await tournaments_repo.get_by_id(session, game.tournament_id)
    minutes_per_game = (
        tournament.period_minutes * tournament.periods_count
        if tournament and tournament.period_minutes and tournament.periods_count
        else None
    )

    def roster_for(team_id: uuid.UUID) -> list[PlayerStatsPublic]:
        """Состав команды именно в этом матче — только отмеченные как игравшие."""
        out = []
        for line in game.stat_lines:
            if line.team_id != team_id:
                continue
            entry = by_player.get(line.player_id)
            team = line.team
            conceded, saves = goalie_values.get(line.player_id, (None, None))
            out.append(
                PlayerStatsPublic(
                    player=_player_ref(line.player, base),
                    team=_team_ref(team.id, team.name, team.logo, base),
                    number=entry.entry.number if entry else None,
                    games=1,
                    goals=line.goals,
                    assists=line.assists,
                    points=line.goals + line.assists,
                    is_goalie=line.is_goalie,
                    goals_against=conceded,
                    saves=saves,
                    minutes_played=minutes_per_game if conceded is not None else None,
                )
            )
        out.sort(key=lambda p: (not p.is_goalie, p.number is None, p.number or 0))
        return out

    names = {line.player_id: line.player for line in game.stat_lines}
    numbers = {pid: (by_player[pid].entry.number if pid in by_player else None) for pid in played}

    goals: list[GoalPublic] = []
    for ev in game.events:
        assists = [names[a] for a in ev.assist_ids if a in names]
        goals.append(
            GoalPublic(
                period=ev.period,
                time=format_clock(ev.time_seconds),
                team_id=str(ev.team_id),
                scorer=_player_ref(names[ev.player_id], base)
                if ev.player_id in names
                else PlayerRef(id=str(ev.player_id), full_name="—"),
                scorer_number=numbers.get(ev.player_id),
                assists=[_player_ref(a, base) for a in assists],
                assist_numbers=[numbers.get(a.id) for a in assists],
            )
        )

    return GameProtocolPublic(
        game=_game_public(game, base),
        roster_a=roster_for(game.team_a_id),
        roster_b=roster_for(game.team_b_id),
        goals=goals,
    )


# ------------------------------------------------------- игроки и бомбардиры


def _roster_stat_public(row, base: str | None) -> PlayerStatsPublic:  # noqa: ANN001
    team = row.entry.team
    return PlayerStatsPublic(
        player=_player_ref(row.entry.player, base),
        team=_team_ref(team.id, team.name, team.logo, base),
        number=row.entry.number,
        games=row.games,
        goals=row.goals,
        assists=row.assists,
        points=row.points,
        is_goalie=row.is_goalie,
        goals_against=row.goals_against,
        saves=row.saves,
        minutes_played=row.minutes_played,
    )


@router.get(
    "/tournaments/{tournament_id}/players",
    response_model=list[PlayerStatsPublic],
    summary="Игроки турнира со статистикой (незаигравшие — с нулями)",
)
async def tournament_players(
    tournament_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> list[PlayerStatsPublic]:
    await _require_visible_tournament(session, tournament_id)
    response.headers["Cache-Control"] = _CACHE_CONTROL
    base = settings.public_base_url
    rows = await stats_service.tournament_players_with_stats(session, tournament_id)
    return [_roster_stat_public(r, base) for r in rows]


@router.get(
    "/tournaments/{tournament_id}/best-players",
    response_model=list[PlayerStatsPublic],
    summary="Бомбардиры турнира по Г+П",
)
async def tournament_best_players(
    tournament_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[PlayerStatsPublic]:
    await _require_visible_tournament(session, tournament_id)
    response.headers["Cache-Control"] = _CACHE_CONTROL
    base = settings.public_base_url
    rows = await stats_service.best_players(session, tournament_id, limit=limit)
    return [
        PlayerStatsPublic(
            player=_player_ref(r.player, base),
            team=_team_ref(r.team.id, r.team.name, r.team.logo, base)
            if r.team is not None
            else TeamRef(id="", name="—"),
            number=r.number,
            games=r.games,
            goals=r.goals,
            assists=r.assists,
            points=r.points,
        )
        for r in rows
    ]


# ------------------------------------------------------------ карточка игрока


@router.get(
    "/players/{player_id}/stats",
    response_model=PlayerCareerPublic,
    summary="Карьера игрока с разбивкой по турнирам и командам",
)
async def player_stats(
    player_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
    tournament_id: Annotated[uuid.UUID | None, Query()] = None,
    team_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PlayerCareerPublic:
    """Фильтры применяются ко всем блокам сразу, а не только к career."""
    breakdown = await stats_service.player_breakdown(
        session,
        player_id,
        tournament_id=tournament_id,
        team_id=team_id,
    )
    if breakdown is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    response.headers["Cache-Control"] = _CACHE_CONTROL
    base = settings.public_base_url

    def totals(t: stats_service.CareerTotals) -> StatTotalsPublic:
        return StatTotalsPublic(
            games=t.games,
            goals=t.goals,
            assists=t.assists,
            points=t.points,
            goals_against=t.goals_against,
            saves=t.saves,
            minutes_played=t.minutes_played,
        )

    return PlayerCareerPublic(
        player=_player_ref(breakdown.player, base),
        career=totals(breakdown.career),
        by_tournament=[
            NamedTotalsPublic(id=str(i), name=n, totals=totals(t))
            for i, n, t in breakdown.by_tournament
        ],
        by_team=[
            NamedTotalsPublic(id=str(i), name=n, totals=totals(t))
            for i, n, t in breakdown.by_team
        ],
    )
