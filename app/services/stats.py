"""Агрегация статистики турнира — всё считается на лету, ничего не хранится.

Доктрина унаследована из timeofthestars-backend-v2: единственный источник истины —
сырые данные (games, game_player_stats, game_events). Таблица, бомбардиры и личная
статистика вычисляются по запросу, поэтому рассинхронизироваться нечему.

Файл разделён на две части:
  * чистое ядро (dataclass'ы + функции без AsyncSession) — его покрывают unit-тесты;
  * обвязка с SQL — тонкая, только запросы и склейка.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, GameEvent, GamePlayerStat
from app.models.player import Player
from app.models.team import Team
from app.models.tournament import Tournament, TournamentTeam
from app.models.tournament_player import TournamentPlayer

WIN_POINTS = 2
DRAW_POINTS = 1

# ============================================================== чистое ядро


@dataclass(frozen=True)
class GameScore:
    """Результат сыгранного матча — минимум, нужный для таблицы и вратарских."""

    team_a_id: uuid.UUID
    team_b_id: uuid.UUID
    score_a: int
    score_b: int
    shots_a: int | None = None
    shots_b: int | None = None


@dataclass
class StandingCore:
    """Строка таблицы до нумерации мест."""

    team_id: uuid.UUID
    name: str
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def points(self) -> int:
        return self.wins * WIN_POINTS + self.draws * DRAW_POINTS

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against


def compute_standings_core(
    teams: list[tuple[uuid.UUID, str]],
    scores: list[GameScore],
) -> list[StandingCore]:
    """Таблица турнира. Стадий нет — в зачёт идут все матчи с заполненным счётом.

    Порядок: очки → разница шайб → забитые шайбы → название (для детерминизма).
    Место = индекс + 1; фронт не пересортировывает.
    """
    rows = {tid: StandingCore(team_id=tid, name=name) for tid, name in teams}

    for s in scores:
        home, away = rows.get(s.team_a_id), rows.get(s.team_b_id)
        # Команда, не заявленная в турнир, в таблицу не попадает (её строки просто нет).
        if home is None or away is None:
            continue
        home.games += 1
        away.games += 1
        home.goals_for += s.score_a
        home.goals_against += s.score_b
        away.goals_for += s.score_b
        away.goals_against += s.score_a
        if s.score_a > s.score_b:
            home.wins += 1
            away.losses += 1
        elif s.score_a < s.score_b:
            away.wins += 1
            home.losses += 1
        else:
            home.draws += 1
            away.draws += 1

    return sorted(
        rows.values(),
        key=lambda r: (-r.points, -r.goal_diff, -r.goals_for, r.name),
    )


def goalie_totals_for_game(score: GameScore, team_id: uuid.UUID) -> tuple[int, int | None]:
    """Вратарские показатели команды в матче: (пропущено, отражено).

    Считаются из «Табло матча», а не вводятся руками:
      пропущено = голы соперника, отражено = броски соперника − голы соперника.
    Отражено = None, если броски соперника в табло не заполнены.
    """
    if team_id == score.team_a_id:
        conceded, opp_shots = score.score_b, score.shots_b
    elif team_id == score.team_b_id:
        conceded, opp_shots = score.score_a, score.shots_a
    else:
        msg = f"Команда {team_id} не участвует в этом матче"
        raise ValueError(msg)

    saves = None if opp_shots is None else max(opp_shots - conceded, 0)
    return conceded, saves


@dataclass
class GoalieAccumulator:
    """Накопитель вратарских по игроку: суммы плюс признак неполноты данных."""

    goals_against: int = 0
    saves: int = 0
    saves_known: bool = True
    minutes_played: int = 0
    games_ambiguous: int = 0


def split_goalie_stats(
    scores_by_game: dict[uuid.UUID, GameScore],
    goalies_by_game_team: dict[tuple[uuid.UUID, uuid.UUID], list[uuid.UUID]],
    minutes_per_game: int | None,
) -> tuple[dict[uuid.UUID, GoalieAccumulator], set[tuple[uuid.UUID, uuid.UUID]]]:
    """Разнести вратарские показатели из табло по конкретным вратарям.

    Броски и голы в бумажном протоколе относятся к команде целиком, поэтому отнести
    их к вратарю можно только когда у команды в матче он ровно ОДИН. Если вратарей
    двое (в бланке под них две строки) — матч не входит в его ПШ/ОБ, а пара
    (game_id, team_id) возвращается вторым значением, чтобы админка это подсветила.
    """
    totals: dict[uuid.UUID, GoalieAccumulator] = {}
    ambiguous: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for (game_id, team_id), goalie_ids in goalies_by_game_team.items():
        score = scores_by_game.get(game_id)
        if score is None:  # матч не сыгран — считать нечего
            continue
        if len(goalie_ids) != 1:
            ambiguous.add((game_id, team_id))
            for gid in goalie_ids:
                totals.setdefault(gid, GoalieAccumulator()).games_ambiguous += 1
            continue

        conceded, saves = goalie_totals_for_game(score, team_id)
        acc = totals.setdefault(goalie_ids[0], GoalieAccumulator())
        acc.goals_against += conceded
        if saves is None:
            acc.saves_known = False
        else:
            acc.saves += saves
        if minutes_per_game:
            acc.minutes_played += minutes_per_game

    return totals, ambiguous


def derive_totals(events: list) -> dict[uuid.UUID, dict[str, int]]:  # noqa: ANN001
    """Голы и передачи из таймлайна.

    Duck-typed: работает и над Pydantic-объектами GameEventIn, и над ORM-строками
    GameEvent — у обоих есть player_id и assist_ids.
    """
    totals: dict[uuid.UUID, dict[str, int]] = {}

    def bucket(pid: uuid.UUID) -> dict[str, int]:
        return totals.setdefault(pid, {"goals": 0, "assists": 0})

    for ev in events:
        bucket(ev.player_id)["goals"] += 1
        for aid in ev.assist_ids:
            bucket(aid)["assists"] += 1

    return totals


# ============================================================== обвязка с SQL


def _agg_columns() -> tuple:
    """Общий набор агрегатов по строкам участия. Игры = число строк протокола."""
    return (
        func.count(GamePlayerStat.id).label("games"),
        func.coalesce(func.sum(GamePlayerStat.goals), 0).label("goals"),
        func.coalesce(func.sum(GamePlayerStat.assists), 0).label("assists"),
    )


async def _tournament_regulation(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> tuple[int | None, int | None]:
    """(period_minutes, periods_count) турнира."""
    stmt = select(Tournament.period_minutes, Tournament.periods_count).where(
        Tournament.id == tournament_id,
    )
    row = (await session.execute(stmt)).one_or_none()
    return (row[0], row[1]) if row else (None, None)


async def _tournament_teams(session: AsyncSession, tournament_id: uuid.UUID) -> list[tuple]:
    """Команды турнира в заданном порядке: (id, name, logo)."""
    stmt = (
        select(Team.id, Team.name, Team.logo)
        .join(TournamentTeam, TournamentTeam.team_id == Team.id)
        .where(TournamentTeam.tournament_id == tournament_id)
        .order_by(TournamentTeam.position)
    )
    return list((await session.execute(stmt)).all())


async def _finished_scores(session: AsyncSession, tournament_id: uuid.UUID) -> list[Game]:
    """Матчи турнира с заполненным счётом."""
    stmt = select(Game).where(
        Game.tournament_id == tournament_id,
        Game.score_a.is_not(None),
        Game.score_b.is_not(None),
    )
    return list((await session.execute(stmt)).scalars().all())


def _to_game_score(g: Game) -> GameScore:
    assert g.score_a is not None and g.score_b is not None
    return GameScore(
        team_a_id=g.team_a_id,
        team_b_id=g.team_b_id,
        score_a=g.score_a,
        score_b=g.score_b,
        shots_a=g.shots_a,
        shots_b=g.shots_b,
    )


async def compute_standings(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> list[tuple[StandingCore, str | None]]:
    """Таблица турнира: список (строка, логотип команды) в порядке мест."""
    teams = await _tournament_teams(session, tournament_id)
    logos = {tid: logo for tid, _, logo in teams}
    games = await _finished_scores(session, tournament_id)
    rows = compute_standings_core(
        [(tid, name) for tid, name, _ in teams],
        [_to_game_score(g) for g in games],
    )
    return [(r, logos.get(r.team_id)) for r in rows]


@dataclass
class RosterStatRow:
    """Игрок заявки со сведённой статистикой (в т.ч. нулевой)."""

    entry: TournamentPlayer
    games: int = 0
    goals: int = 0
    assists: int = 0
    is_goalie: bool = False
    goals_against: int | None = None
    saves: int | None = None
    minutes_played: int | None = None

    @property
    def points(self) -> int:
        return self.goals + self.assists


async def _goalie_map(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> dict[tuple[uuid.UUID, uuid.UUID], list[uuid.UUID]]:
    """(game_id, team_id) → список вратарей в этом матче."""
    stmt = (
        select(GamePlayerStat.game_id, GamePlayerStat.team_id, GamePlayerStat.player_id)
        .join(Game, Game.id == GamePlayerStat.game_id)
        .where(Game.tournament_id == tournament_id, GamePlayerStat.is_goalie.is_(True))
    )
    out: dict[tuple[uuid.UUID, uuid.UUID], list[uuid.UUID]] = {}
    for game_id, team_id, player_id in (await session.execute(stmt)).all():
        out.setdefault((game_id, team_id), []).append(player_id)
    return out


async def tournament_players_with_stats(
    session: AsyncSession,
    tournament_id: uuid.UUID,
) -> list[RosterStatRow]:
    """Заявка турнира + статистика. Незаигравшие возвращаются с нулями, а не пропадают."""
    from app.repositories import tournament_players as roster_repo

    entries = await roster_repo.list_for_tournament(session, tournament_id)

    # Один сгруппированный агрегат по (player_id, team_id) — без N+1.
    agg_stmt = (
        select(GamePlayerStat.player_id, GamePlayerStat.team_id, *_agg_columns())
        .join(Game, Game.id == GamePlayerStat.game_id)
        .where(Game.tournament_id == tournament_id)
        .group_by(GamePlayerStat.player_id, GamePlayerStat.team_id)
    )
    agg = {
        (pid, tid): (games, goals, assists)
        for pid, tid, games, goals, assists in (await session.execute(agg_stmt)).all()
    }

    goalie_stmt = (
        select(GamePlayerStat.player_id)
        .join(Game, Game.id == GamePlayerStat.game_id)
        .where(Game.tournament_id == tournament_id, GamePlayerStat.is_goalie.is_(True))
        .distinct()
    )
    goalie_ids = set((await session.execute(goalie_stmt)).scalars().all())

    period_minutes, periods_count = await _tournament_regulation(session, tournament_id)
    minutes_per_game = (
        period_minutes * periods_count if period_minutes and periods_count else None
    )
    games = await _finished_scores(session, tournament_id)
    goalie_totals, _ = split_goalie_stats(
        {g.id: _to_game_score(g) for g in games},
        await _goalie_map(session, tournament_id),
        minutes_per_game,
    )

    rows: list[RosterStatRow] = []
    for entry in entries:
        g, go, a = agg.get((entry.player_id, entry.team_id), (0, 0, 0))
        row = RosterStatRow(
            entry=entry,
            games=g,
            goals=go,
            assists=a,
            is_goalie=entry.player_id in goalie_ids,
        )
        acc = goalie_totals.get(entry.player_id)
        if row.is_goalie and acc is not None:
            row.goals_against = acc.goals_against
            row.saves = acc.saves if acc.saves_known else None
            row.minutes_played = acc.minutes_played or None
        rows.append(row)
    return rows


@dataclass
class BestPlayerRow:
    """Строка списка бомбардиров. team заполняется — в v2 это был известный баг."""

    player: Player
    team: Team | None
    number: int | None
    games: int
    goals: int
    assists: int

    @property
    def points(self) -> int:
        return self.goals + self.assists


async def best_players(
    session: AsyncSession,
    tournament_id: uuid.UUID,
    limit: int = 10,
) -> list[BestPlayerRow]:
    """Лидеры турнира по Г+П.

    Переиспользует агрегат заявки (один сгруппированный запрос) и сортирует уже
    в Python: набор игроков турнира невелик, а дублировать SQL смысла нет.
    Незаигравшие в список не попадают. Команда заполняется — в v2 team_id
    у бомбардиров всегда приходил null, повторять этот дефект не надо.
    """
    rows = await tournament_players_with_stats(session, tournament_id)
    played = [r for r in rows if r.games > 0]
    played.sort(
        key=lambda r: (-r.points, -r.goals, r.entry.player.full_name),
    )
    return [
        BestPlayerRow(
            player=r.entry.player,
            team=r.entry.team,
            number=r.entry.number,
            games=r.games,
            goals=r.goals,
            assists=r.assists,
        )
        for r in played[:limit]
    ]


@dataclass
class CareerTotals:
    games: int = 0
    goals: int = 0
    assists: int = 0

    @property
    def points(self) -> int:
        return self.goals + self.assists


@dataclass
class PlayerBreakdown:
    player: Player
    career: CareerTotals
    by_tournament: list[tuple[uuid.UUID, str, CareerTotals]] = field(default_factory=list)
    by_team: list[tuple[uuid.UUID, str, CareerTotals]] = field(default_factory=list)


async def player_breakdown(
    session: AsyncSession,
    player_id: uuid.UUID,
    *,
    tournament_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
) -> PlayerBreakdown | None:
    """Карьера игрока + разбивка по турнирам и командам.

    Фильтры применяются ко ВСЕМ трём блокам, а не только к career — в v2 это
    расхождение было задокументированным дефектом API.
    """
    player = (
        await session.execute(select(Player).where(Player.id == player_id))
    ).scalar_one_or_none()
    if player is None:
        return None

    def _filtered(stmt):  # noqa: ANN001, ANN202
        stmt = stmt.join(Game, Game.id == GamePlayerStat.game_id).where(
            GamePlayerStat.player_id == player_id,
        )
        if tournament_id is not None:
            stmt = stmt.where(Game.tournament_id == tournament_id)
        if team_id is not None:
            stmt = stmt.where(GamePlayerStat.team_id == team_id)
        return stmt

    career_row = (await session.execute(_filtered(select(*_agg_columns())))).one()
    career = CareerTotals(games=career_row[0], goals=career_row[1], assists=career_row[2])

    by_tour_stmt = _filtered(
        select(Tournament.id, Tournament.title, *_agg_columns()),
    ).join(Tournament, Tournament.id == Game.tournament_id).group_by(
        Tournament.id, Tournament.title,
    ).order_by(Tournament.title)
    by_tournament = [
        (tid, title, CareerTotals(games=g, goals=go, assists=a))
        for tid, title, g, go, a in (await session.execute(by_tour_stmt)).all()
    ]

    by_team_stmt = _filtered(
        select(Team.id, Team.name, *_agg_columns()),
    ).join(Team, Team.id == GamePlayerStat.team_id).group_by(Team.id, Team.name).order_by(
        Team.name,
    )
    by_team = [
        (tid, name, CareerTotals(games=g, goals=go, assists=a))
        for tid, name, g, go, a in (await session.execute(by_team_stmt)).all()
    ]

    return PlayerBreakdown(
        player=player,
        career=career,
        by_tournament=by_tournament,
        by_team=by_team,
    )


async def goals_timeline(session: AsyncSession, game_id: uuid.UUID) -> list[GameEvent]:
    """Таймлайн голов матча с подгруженными игроками (для протокола)."""
    stmt = (
        select(GameEvent)
        .where(GameEvent.game_id == game_id)
        .order_by(GameEvent.period, GameEvent.sort_order, GameEvent.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())
