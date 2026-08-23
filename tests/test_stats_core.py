"""Чистое ядро статистики: таблица, вратарские из табло, вывод голов/передач.

Числа взяты из настоящего бумажного протокола турнира «Летний кубок», матч №1:
ХК «ИСКРА» — ХК «ИМПУЛЬС», табло 1:8, броски 8:26.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from app.services.stats import (
    GameScore,
    compute_standings_core,
    derive_totals,
    goalie_totals_for_game,
    split_goalie_stats,
)

ISKRA = uuid.uuid4()
IMPULS = uuid.uuid4()
THIRD = uuid.uuid4()

TEAMS = [(ISKRA, "ХК «ИСКРА»"), (IMPULS, "ХК «ИМПУЛЬС»")]
MATCH_1 = GameScore(team_a_id=ISKRA, team_b_id=IMPULS, score_a=1, score_b=8, shots_a=8, shots_b=26)


# ------------------------------------------------------------------- таблица


def test_standings_single_game() -> None:
    rows = compute_standings_core(TEAMS, [MATCH_1])
    winner, loser = rows

    assert winner.team_id == IMPULS
    assert (winner.wins, winner.draws, winner.losses) == (1, 0, 0)
    assert winner.points == 2
    assert winner.goal_diff == 7

    assert loser.team_id == ISKRA
    assert (loser.wins, loser.draws, loser.losses) == (0, 0, 1)
    assert loser.points == 0
    assert loser.goal_diff == -7


def test_standings_draw_gives_one_point_each() -> None:
    rows = compute_standings_core(
        TEAMS,
        [GameScore(team_a_id=ISKRA, team_b_id=IMPULS, score_a=3, score_b=3)],
    )
    assert [r.points for r in rows] == [1, 1]
    assert all(r.draws == 1 and r.games == 1 for r in rows)


def test_standings_team_without_games_is_listed_with_zeros() -> None:
    """Заявленная команда без матчей должна быть в таблице, а не отсутствовать."""
    rows = compute_standings_core([*TEAMS, (THIRD, "ХК «ТРЕТИЙ»")], [MATCH_1])
    third = next(r for r in rows if r.team_id == THIRD)
    assert (third.games, third.points, third.goal_diff) == (0, 0, 0)
    # При равных очках (0) порядок решает разница шайб: 0 у команды без матчей
    # лучше, чем −7 у проигравшей. Это следствие заявленной цепочки tie-break.
    assert [r.team_id for r in rows] == [IMPULS, THIRD, ISKRA]


def test_standings_ignores_teams_not_in_tournament() -> None:
    """Матч с незаявленной командой не должен ломать таблицу."""
    rows = compute_standings_core(
        [(ISKRA, "ХК «ИСКРА»")],
        [GameScore(team_a_id=ISKRA, team_b_id=IMPULS, score_a=5, score_b=0)],
    )
    assert len(rows) == 1
    assert rows[0].games == 0  # матч не зачтён: соперника нет в турнире


def test_standings_tiebreak_order() -> None:
    """Очки → разница шайб → забитые → название."""
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    teams = [(a, "A"), (b, "B"), (c, "C"), (d, "D")]
    scores = [
        # A: победа 5:0 → 2 очка, разница +5
        GameScore(team_a_id=a, team_b_id=d, score_a=5, score_b=0),
        # B: победа 3:1 → 2 очка, разница +2, забито 3
        GameScore(team_a_id=b, team_b_id=d, score_a=3, score_b=1),
        # C: победа 2:0 → 2 очка, разница +2, забито 2
        GameScore(team_a_id=c, team_b_id=d, score_a=2, score_b=0),
    ]
    rows = compute_standings_core(teams, scores)
    assert [r.name for r in rows] == ["A", "B", "C", "D"]
    assert rows[1].goal_diff == rows[2].goal_diff  # B и C равны по разнице
    assert rows[1].goals_for > rows[2].goals_for  # разошлись по забитым


# ---------------------------------------------------------------- вратарские


def test_goalie_totals_from_scoreboard() -> None:
    """Пропущено = голы соперника, отражено = броски соперника − его голы."""
    conceded_iskra, saves_iskra = goalie_totals_for_game(MATCH_1, ISKRA)
    assert (conceded_iskra, saves_iskra) == (8, 26 - 8)  # Едигарев: ПШ 8, ОБ 18

    conceded_impuls, saves_impuls = goalie_totals_for_game(MATCH_1, IMPULS)
    assert (conceded_impuls, saves_impuls) == (1, 8 - 1)  # Малахов: ПШ 1, ОБ 7


def test_goalie_saves_unknown_without_shots() -> None:
    score = GameScore(team_a_id=ISKRA, team_b_id=IMPULS, score_a=1, score_b=8)
    conceded, saves = goalie_totals_for_game(score, ISKRA)
    assert conceded == 8
    assert saves is None  # броски в табло не заполнены — отражённые неизвестны


def test_goalie_totals_rejects_foreign_team() -> None:
    with pytest.raises(ValueError, match="не участвует"):
        goalie_totals_for_game(MATCH_1, THIRD)


def test_split_goalie_stats_single_goalie() -> None:
    game_id = uuid.uuid4()
    edigarev, malakhov = uuid.uuid4(), uuid.uuid4()
    totals, ambiguous = split_goalie_stats(
        {game_id: MATCH_1},
        {(game_id, ISKRA): [edigarev], (game_id, IMPULS): [malakhov]},
        minutes_per_game=45,
    )
    assert not ambiguous
    assert totals[edigarev].goals_against == 8
    assert totals[edigarev].saves == 18
    assert totals[edigarev].saves_known is True
    assert totals[edigarev].minutes_played == 45
    assert (totals[malakhov].goals_against, totals[malakhov].saves) == (1, 7)


def test_split_goalie_stats_two_goalies_is_not_attributed() -> None:
    """Табло относится к команде целиком: с двумя вратарями делить нечем."""
    game_id = uuid.uuid4()
    g1, g2 = uuid.uuid4(), uuid.uuid4()
    totals, ambiguous = split_goalie_stats(
        {game_id: MATCH_1},
        {(game_id, ISKRA): [g1, g2]},
        minutes_per_game=45,
    )
    assert (game_id, ISKRA) in ambiguous
    assert totals[g1].goals_against == 0
    assert totals[g1].games_ambiguous == 1
    assert totals[g2].games_ambiguous == 1


def test_split_goalie_stats_skips_unplayed_game() -> None:
    game_id = uuid.uuid4()
    totals, ambiguous = split_goalie_stats({}, {(game_id, ISKRA): [uuid.uuid4()]}, 45)
    assert not totals
    assert not ambiguous


def test_split_goalie_stats_saves_unknown_marks_flag() -> None:
    game_id = uuid.uuid4()
    goalie = uuid.uuid4()
    totals, _ = split_goalie_stats(
        {game_id: GameScore(team_a_id=ISKRA, team_b_id=IMPULS, score_a=1, score_b=8)},
        {(game_id, ISKRA): [goalie]},
        minutes_per_game=None,
    )
    assert totals[goalie].goals_against == 8
    assert totals[goalie].saves_known is False
    assert totals[goalie].minutes_played == 0


# ------------------------------------------------- вывод голов/передач из событий


@dataclass
class FakeEvent:
    """Duck-type под GameEventIn/GameEvent: нужны только player_id и assist_ids."""

    player_id: uuid.UUID
    assist_ids: list[uuid.UUID]


def test_derive_totals_impuls_goals_from_paper() -> None:
    """8 голов ИМПУЛЬСА из бланка: №13 забивает 4 раза, №12 — 1 гол и 2 передачи."""
    n13, n12, n3, n7, n9, n2, n11 = (uuid.uuid4() for _ in range(7))
    events = [
        FakeEvent(n12, [n2]),   # 13:36
        FakeEvent(n3, []),      # 12:36
        FakeEvent(n13, [n12]),  # 08:46
        FakeEvent(n7, [n11]),   # 07:19
        FakeEvent(n13, []),     # 04:15
        FakeEvent(n13, []),     # 14:15
        FakeEvent(n13, [n9]),   # 09:29
        FakeEvent(n9, [n12]),   # 08:42
    ]
    totals = derive_totals(events)

    # №13 — автор строк 3, 5, 6, 7 бланка; передач у него нет.
    assert totals[n13] == {"goals": 4, "assists": 0}
    # №12 — гол в строке 1 и передачи в строках 3 и 8.
    assert totals[n12] == {"goals": 1, "assists": 2}
    assert totals[n9] == {"goals": 1, "assists": 1}
    assert totals[n3] == {"goals": 1, "assists": 0}
    assert totals[n7] == {"goals": 1, "assists": 0}
    assert totals[n2] == {"goals": 0, "assists": 1}
    assert totals[n11] == {"goals": 0, "assists": 1}
    assert sum(t["goals"] for t in totals.values()) == 8
    # Передачи есть в строках 1, 3, 4, 7, 8 бланка.
    assert sum(t["assists"] for t in totals.values()) == 5


def test_derive_totals_two_assists_credit_both() -> None:
    scorer, a1, a2 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    totals = derive_totals([FakeEvent(scorer, [a1, a2])])
    assert totals[scorer]["goals"] == 1
    assert totals[a1]["assists"] == 1
    assert totals[a2]["assists"] == 1


def test_derive_totals_empty_timeline() -> None:
    assert derive_totals([]) == {}
