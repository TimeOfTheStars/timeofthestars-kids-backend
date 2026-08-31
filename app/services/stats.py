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

from sqlalchemy import and_, case, distinct, func, select, union_all
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
    # Сколько матчей реально зачтено. Ноль означает «неизвестно», а не «сухие матчи»:
    # у команды в каждом матче было ноль или больше одного вратаря.
    games_counted: int = 0
    games_ambiguous: int = 0

    @property
    def has_data(self) -> bool:
        """Есть ли хотя бы один матч, который удалось отнести к этому вратарю."""
        return self.games_counted > 0


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
        acc.games_counted += 1
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


# --- общая статистика команды за всю историю ---

# Показатели, которые можно переопределить руками. Порядок = порядок в кабинете.
TEAM_STAT_FIELDS = (
    "tournaments",
    "games",
    "wins",
    "draws",
    "losses",
    "goals_for",
    "goals_against",
)


@dataclass
class TeamCareer:
    """Общая статистика команды по всем турнирам."""

    tournaments: int = 0
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def points(self) -> int:
        """Очки от ДЕЙСТВУЮЩИХ побед и ничьих — отдельной колонкой не хранятся."""
        return self.wins * WIN_POINTS + self.draws * DRAW_POINTS

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against


def apply_corrections(
    computed: TeamCareer,
    corrections: dict[str, int | None],
) -> tuple[TeamCareer, set[str]]:
    """Итог = расчёт по матчам + поправка. Возвращает (итог, поля с поправкой).

    Поправка — это матчи, которых в системе нет (старые турниры). Модель именно
    складывающая, а не замещающая: новые заведённые матчи попадают в итог сами,
    а внесённая правка при этом не устаревает.

    None и 0 равнозначны «поправки нет»; 0 не считается правкой, чтобы кабинет
    не подсвечивал поле, где ничего не менялось. Поправка может быть
    отрицательной — иначе итог нельзя было бы уменьшить.

    Очки не поправляются: они выводятся из итоговых побед и ничьих.
    """
    effective = TeamCareer(**{f: getattr(computed, f) for f in TEAM_STAT_FIELDS})
    corrected: set[str] = set()

    for field_name in TEAM_STAT_FIELDS:
        delta = corrections.get(field_name) or 0
        if delta == 0:
            continue
        setattr(effective, field_name, getattr(computed, field_name) + delta)
        corrected.add(field_name)

    return effective, corrected


def corrections_from_team(team: Team) -> dict[str, int | None]:
    """Прочитать колонки extra_* команды в вид, который ждёт apply_corrections."""
    return {f: getattr(team, f"extra_{f}") for f in TEAM_STAT_FIELDS}


def corrections_for_totals(
    computed: TeamCareer,
    totals: dict[str, int | None],
) -> dict[str, int | None]:
    """Перевести желаемые ИТОГИ в поправки, которые нужно сохранить.

    Кабинет показывает и принимает итог («у команды 23 игры»), а хранится
    поправка, чтобы новые матчи продолжали учитываться. None на входе означает
    «убрать поправку», то есть вернуться к чистому расчёту.
    """
    out: dict[str, int | None] = {}
    for field_name, total in totals.items():
        if field_name not in TEAM_STAT_FIELDS:
            continue
        if total is None:
            out[field_name] = None
            continue
        delta = total - getattr(computed, field_name)
        out[field_name] = delta or None
    return out


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


async def _tournament_teams(session: AsyncSession, tournament_id: uuid.UUID) -> list[Team]:
    """Команды турнира в заданном порядке — целыми объектами.

    Раньше выбирались кортежи (id, name, logo), и каждое новое поле команды
    приходилось протаскивать через compute_standings и роут. С объектом Team
    добавление поля больше эту цепочку не задевает.
    """
    stmt = (
        select(Team)
        .join(TournamentTeam, TournamentTeam.team_id == Team.id)
        .where(TournamentTeam.tournament_id == tournament_id)
        .order_by(TournamentTeam.position)
    )
    return list((await session.execute(stmt)).scalars().all())


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
) -> list[tuple[StandingCore, Team]]:
    """Таблица турнира: список (строка таблицы, команда) в порядке мест."""
    teams = await _tournament_teams(session, tournament_id)
    by_id = {t.id: t for t in teams}
    games = await _finished_scores(session, tournament_id)
    rows = compute_standings_core(
        [(t.id, t.name) for t in teams],
        [_to_game_score(g) for g in games],
    )
    return [(r, by_id[r.team_id]) for r in rows]


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
        # has_data: если ни один матч не удалось отнести к вратарю (в каждом было
        # ноль или два вратаря), показатели остаются None — «неизвестно».
        # Ноль здесь читался бы как сухие матчи.
        if row.is_goalie and acc is not None and acc.has_data:
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


async def goalie_totals_for_player(
    session: AsyncSession,
    player_id: uuid.UUID,
    *,
    tournament_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
) -> tuple[GoalieAccumulator, dict[uuid.UUID, GoalieAccumulator], dict[uuid.UUID, GoalieAccumulator]]:
    """Вратарские показатели игрока: (карьера, по турнирам, по командам).

    Считаются из «Табло матча», а не хранятся. Матч учитывается только если игрок
    был в нём ЕДИНСТВЕННЫМ вратарём своей команды — броски и голы в бланке
    относятся к команде целиком (см. split_goalie_stats).
    """
    stmt = (
        select(
            Game.id,
            Game.tournament_id,
            GamePlayerStat.team_id,
            Game.team_a_id,
            Game.score_a,
            Game.score_b,
            Game.shots_a,
            Game.shots_b,
            Tournament.period_minutes,
            Tournament.periods_count,
        )
        .join(Game, Game.id == GamePlayerStat.game_id)
        .join(Tournament, Tournament.id == Game.tournament_id)
        .where(
            GamePlayerStat.player_id == player_id,
            GamePlayerStat.is_goalie.is_(True),
            Game.score_a.is_not(None),
            Game.score_b.is_not(None),
        )
    )
    if tournament_id is not None:
        stmt = stmt.where(Game.tournament_id == tournament_id)
    if team_id is not None:
        stmt = stmt.where(GamePlayerStat.team_id == team_id)
    rows = (await session.execute(stmt)).all()

    career = GoalieAccumulator()
    by_tournament: dict[uuid.UUID, GoalieAccumulator] = {}
    by_team: dict[uuid.UUID, GoalieAccumulator] = {}
    if not rows:
        return career, by_tournament, by_team

    # Сколько вратарей было у команды в каждом из этих матчей.
    counts_stmt = (
        select(GamePlayerStat.game_id, GamePlayerStat.team_id, func.count(GamePlayerStat.id))
        .where(
            GamePlayerStat.game_id.in_([r[0] for r in rows]),
            GamePlayerStat.is_goalie.is_(True),
        )
        .group_by(GamePlayerStat.game_id, GamePlayerStat.team_id)
    )
    goalie_counts = {
        (gid, tid): int(cnt) for gid, tid, cnt in (await session.execute(counts_stmt)).all()
    }

    for (
        game_id,
        tour_id,
        own_team_id,
        team_a_id,
        score_a,
        score_b,
        shots_a,
        shots_b,
        period_minutes,
        periods_count,
    ) in rows:
        targets = [
            career,
            by_tournament.setdefault(tour_id, GoalieAccumulator()),
            by_team.setdefault(own_team_id, GoalieAccumulator()),
        ]
        if goalie_counts.get((game_id, own_team_id), 0) != 1:
            for acc in targets:
                acc.games_ambiguous += 1
            continue
        for acc in targets:
            acc.games_counted += 1

        is_home = own_team_id == team_a_id
        conceded = score_b if is_home else score_a
        opp_shots = shots_b if is_home else shots_a
        saves = None if opp_shots is None else max(opp_shots - conceded, 0)
        minutes = (
            period_minutes * periods_count if period_minutes and periods_count else 0
        )
        for acc in targets:
            acc.goals_against += conceded
            if saves is None:
                acc.saves_known = False
            else:
                acc.saves += saves
            acc.minutes_played += minutes

    return career, by_tournament, by_team


@dataclass
class CareerTotals:
    games: int = 0
    goals: int = 0
    assists: int = 0
    # Вратарские: None у полевых игроков и там, где табло не даёт их распределить.
    goals_against: int | None = None
    saves: int | None = None
    minutes_played: int | None = None

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

    # Вратарские считаются из табло отдельным проходом и подмешиваются в те же блоки.
    g_career, g_by_tour, g_by_team = await goalie_totals_for_player(
        session,
        player_id,
        tournament_id=tournament_id,
        team_id=team_id,
    )

    def _apply(totals: CareerTotals, acc: GoalieAccumulator | None) -> CareerTotals:
        # Без зачтённых матчей вратарские остаются None — «неизвестно», а не нули.
        if acc is None or not acc.has_data:
            return totals
        totals.goals_against = acc.goals_against
        totals.saves = acc.saves if acc.saves_known else None
        totals.minutes_played = acc.minutes_played or None
        return totals

    _apply(career, g_career)
    by_tournament = [(i, n, _apply(t, g_by_tour.get(i))) for i, n, t in by_tournament]
    by_team = [(i, n, _apply(t, g_by_team.get(i))) for i, n, t in by_team]

    return PlayerBreakdown(
        player=player,
        career=career,
        by_tournament=by_tournament,
        by_team=by_team,
    )


def _team_games_subquery():  # noqa: ANN202 — SQLAlchemy subquery
    """Сыгранные матчи в виде строк на КАЖДУЮ команду.

    Команда бывает и team_a, и team_b, поэтому нормализуем через UNION ALL двух
    выборок к общему виду (team_id, tournament_id, забито, пропущено, В, Н, П).
    Так вся общая статистика считается одним группированным запросом.
    """
    played = and_(Game.score_a.is_not(None), Game.score_b.is_not(None))

    def side(team_col, own, opp):  # noqa: ANN001, ANN202
        return select(
            team_col.label("team_id"),
            Game.tournament_id.label("tournament_id"),
            own.label("goals_for"),
            opp.label("goals_against"),
            case((own > opp, 1), else_=0).label("win"),
            case((own == opp, 1), else_=0).label("draw"),
            case((own < opp, 1), else_=0).label("loss"),
        ).where(played)

    return union_all(
        side(Game.team_a_id, Game.score_a, Game.score_b),
        side(Game.team_b_id, Game.score_b, Game.score_a),
    ).subquery()


async def team_career_stats_bulk(
    session: AsyncSession,
    team_ids: list[uuid.UUID] | None = None,
) -> dict[uuid.UUID, TeamCareer]:
    """Рассчитанная общая статистика по всем командам одним запросом (без N+1).

    Команды без сыгранных матчей в результат не попадают — вызывающий код должен
    считать их отсутствие нулями (см. TeamCareer по умолчанию).
    «Турниров играла» = число турниров, где есть хотя бы один матч со счётом.
    """
    sq = _team_games_subquery()
    stmt = (
        select(
            sq.c.team_id,
            func.count(distinct(sq.c.tournament_id)).label("tournaments"),
            func.count().label("games"),
            func.coalesce(func.sum(sq.c.win), 0).label("wins"),
            func.coalesce(func.sum(sq.c.draw), 0).label("draws"),
            func.coalesce(func.sum(sq.c.loss), 0).label("losses"),
            func.coalesce(func.sum(sq.c.goals_for), 0).label("goals_for"),
            func.coalesce(func.sum(sq.c.goals_against), 0).label("goals_against"),
        )
        .group_by(sq.c.team_id)
    )
    if team_ids is not None:
        if not team_ids:
            return {}
        stmt = stmt.where(sq.c.team_id.in_(team_ids))

    return {
        row.team_id: TeamCareer(
            tournaments=int(row.tournaments),
            games=int(row.games),
            wins=int(row.wins),
            draws=int(row.draws),
            losses=int(row.losses),
            goals_for=int(row.goals_for),
            goals_against=int(row.goals_against),
        )
        for row in (await session.execute(stmt)).all()
    }


async def team_career_stats(session: AsyncSession, team_id: uuid.UUID) -> TeamCareer:
    """Рассчитанная статистика одной команды. Без матчей — нули."""
    found = await team_career_stats_bulk(session, [team_id])
    return found.get(team_id, TeamCareer())


async def team_effective_stats(
    session: AsyncSession,
    teams: list[Team],
) -> dict[uuid.UUID, tuple[TeamCareer, TeamCareer, set[str]]]:
    """Для списка команд: (итог, расчёт по матчам, поля с поправкой)."""
    computed = await team_career_stats_bulk(session, [t.id for t in teams])
    out: dict[uuid.UUID, tuple[TeamCareer, TeamCareer, set[str]]] = {}
    for team in teams:
        base = computed.get(team.id, TeamCareer())
        effective, corrected = apply_corrections(base, corrections_from_team(team))
        out[team.id] = (effective, base, corrected)
    return out


async def goals_timeline(session: AsyncSession, game_id: uuid.UUID) -> list[GameEvent]:
    """Таймлайн голов матча с подгруженными игроками (для протокола)."""
    stmt = (
        select(GameEvent)
        .where(GameEvent.game_id == game_id)
        .order_by(GameEvent.period, GameEvent.sort_order, GameEvent.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())
