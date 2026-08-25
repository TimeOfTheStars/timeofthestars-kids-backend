"""Общая статистика команды: расчёт по матчам плюс поправка.

Модель складывающая, а не замещающая: поправка — это матчи вне системы (старые
турниры), поэтому новые заведённые матчи продолжают попадать в итог сами, а
внесённая правка не устаревает. Тесты закрепляют именно это.
"""

from __future__ import annotations

import pytest

from app.services.stats import (
    DRAW_POINTS,
    TEAM_STAT_FIELDS,
    WIN_POINTS,
    TeamCareer,
    apply_corrections,
    corrections_for_totals,
)

# Локомотив на «Летнем Кубке»: 3 игры, 1 победа, 2 поражения, 13-13.
LOKO = TeamCareer(
    tournaments=1, games=3, wins=1, draws=0, losses=2, goals_for=13, goals_against=13,
)
# Тот же Локомотив после ещё одного матча — 5:1.
LOKO_GROWN = TeamCareer(
    tournaments=1, games=4, wins=2, draws=0, losses=2, goals_for=18, goals_against=14,
)


def test_points_and_diff_are_derived() -> None:
    assert LOKO.points == 1 * WIN_POINTS
    assert LOKO.goal_diff == 0
    assert TeamCareer(wins=3, draws=1).points == 3 * WIN_POINTS + DRAW_POINTS


def test_no_corrections_keeps_computed() -> None:
    effective, corrected = apply_corrections(LOKO, dict.fromkeys(TEAM_STAT_FIELDS))
    assert corrected == set()
    assert effective == LOKO


def test_zero_correction_is_not_a_correction() -> None:
    """0 и None равнозначны: подсвечивать поле, где ничего не менялось, незачем."""
    effective, corrected = apply_corrections(LOKO, {"games": 0})
    assert corrected == set()
    assert effective.games == LOKO.games


def test_correction_is_added_to_computed() -> None:
    effective, corrected = apply_corrections(LOKO, {"games": 20, "wins": 12})
    assert corrected == {"games", "wins"}
    assert (effective.games, effective.wins) == (23, 13)
    # Показатели без поправки остались как рассчитаны.
    assert (effective.draws, effective.losses) == (0, 2)


def test_negative_correction_allowed() -> None:
    """Без отрицательной поправки итог нельзя было бы уменьшить."""
    effective, corrected = apply_corrections(LOKO, {"games": -1})
    assert effective.games == 2
    assert corrected == {"games"}


def test_points_follow_effective_totals() -> None:
    effective, _ = apply_corrections(LOKO, {"wins": 12, "draws": 4})
    assert effective.points == 13 * WIN_POINTS + 4 * DRAW_POINTS


def test_correction_does_not_mutate_computed() -> None:
    before = (LOKO.games, LOKO.wins)
    apply_corrections(LOKO, {"games": 99, "wins": 99})
    assert (LOKO.games, LOKO.wins) == before


def test_new_match_keeps_being_counted() -> None:
    """Главное отличие от прежней модели: итог продолжает расти.

    Администратор задал итог «23 игры, 13 побед» при расчёте 3/1 — сохранилась
    поправка +20/+12. После нового матча (расчёт 4/2) итог обязан стать 24/14,
    а не остаться 23/13.
    """
    deltas = corrections_for_totals(LOKO, {"games": 23, "wins": 13})
    assert deltas == {"games": 20, "wins": 12}

    now, _ = apply_corrections(LOKO, deltas)
    assert (now.games, now.wins) == (23, 13)

    later, _ = apply_corrections(LOKO_GROWN, deltas)
    assert (later.games, later.wins) == (24, 14)


def test_totals_to_corrections_roundtrip() -> None:
    """Заданный итог должен воспроизводиться на том же расчёте."""
    totals = {f: 50 for f in TEAM_STAT_FIELDS}
    deltas = corrections_for_totals(LOKO, totals)
    effective, corrected = apply_corrections(LOKO, deltas)
    for field in TEAM_STAT_FIELDS:
        assert getattr(effective, field) == 50
    assert corrected == set(TEAM_STAT_FIELDS)


def test_total_equal_to_computed_stores_no_correction() -> None:
    """Если итог совпал с расчётом, поправка не нужна — поле остаётся чистым."""
    deltas = corrections_for_totals(LOKO, {"games": LOKO.games})
    assert deltas == {"games": None}
    _, corrected = apply_corrections(LOKO, deltas)
    assert corrected == set()


def test_none_total_clears_correction() -> None:
    assert corrections_for_totals(LOKO, {"games": None}) == {"games": None}


@pytest.mark.parametrize("field", TEAM_STAT_FIELDS)
def test_every_field_is_correctable(field: str) -> None:
    deltas = corrections_for_totals(LOKO, {field: 77})
    effective, corrected = apply_corrections(LOKO, deltas)
    assert corrected == {field}
    assert getattr(effective, field) == 77
