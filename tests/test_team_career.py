"""Общая статистика команды и семантика ручной перезаписи.

Перезапись выбрана осознанно: вписанное значение заменяет расчёт и НЕ
пересчитывается при новых матчах. Тесты закрепляют именно это поведение,
включая устаревание, — чтобы его не «починили» случайно.
"""

from __future__ import annotations

import pytest

from app.services.stats import (
    DRAW_POINTS,
    TEAM_STAT_FIELDS,
    WIN_POINTS,
    TeamCareer,
    apply_manual_overrides,
)

# Локомотив на «Летнем Кубке»: 3 игры, 1 победа, 2 поражения, 13-13.
LOKO = TeamCareer(
    tournaments=1, games=3, wins=1, draws=0, losses=2, goals_for=13, goals_against=13,
)


def test_points_and_diff_are_derived() -> None:
    assert LOKO.points == 1 * WIN_POINTS + 0 * DRAW_POINTS
    assert LOKO.goal_diff == 0
    assert TeamCareer(wins=3, draws=1).points == 3 * WIN_POINTS + DRAW_POINTS


def test_empty_career_is_all_zeros() -> None:
    empty = TeamCareer()
    assert (empty.games, empty.points, empty.goal_diff) == (0, 0, 0)


def test_no_overrides_keeps_computed() -> None:
    effective, manual = apply_manual_overrides(LOKO, dict.fromkeys(TEAM_STAT_FIELDS))
    assert manual == set()
    assert effective == LOKO


def test_override_replaces_only_named_fields() -> None:
    effective, manual = apply_manual_overrides(LOKO, {"games": 23, "wins": 13})
    assert manual == {"games", "wins"}
    assert (effective.games, effective.wins) == (23, 13)
    # Не переопределённые поля остались рассчитанными.
    assert (effective.draws, effective.losses) == (0, 2)
    assert (effective.goals_for, effective.goals_against) == (13, 13)


def test_points_follow_effective_not_computed() -> None:
    """Очки не переопределяются: считаются от действующих побед и ничьих."""
    effective, _ = apply_manual_overrides(LOKO, {"wins": 13, "draws": 4})
    assert effective.points == 13 * WIN_POINTS + 4 * DRAW_POINTS
    assert effective.points != LOKO.points


def test_override_does_not_mutate_computed() -> None:
    """Рассчитанное значение нужно показать рядом, поэтому портить его нельзя."""
    before = (LOKO.games, LOKO.wins)
    apply_manual_overrides(LOKO, {"games": 99, "wins": 99})
    assert (LOKO.games, LOKO.wins) == before


def test_override_survives_growth_of_computed() -> None:
    """Устаревание — принятое поведение, а не дефект.

    Команда сыграла ещё матч (расчёт вырос с 3 до 4), но вписанное И осталось 23.
    """
    grown = TeamCareer(
        tournaments=1, games=4, wins=2, draws=0, losses=2, goals_for=18, goals_against=14,
    )
    effective, manual = apply_manual_overrides(grown, {"games": 23})
    assert effective.games == 23
    assert grown.games == 4
    assert manual == {"games"}
    # Не переопределённые показатели при этом подхватили новый матч.
    assert effective.wins == 2


def test_zero_is_a_real_override_not_absence() -> None:
    """0 — валидное вписанное значение и должен подменять расчёт, в отличие от None."""
    effective, manual = apply_manual_overrides(LOKO, {"games": 0})
    assert effective.games == 0
    assert manual == {"games"}


@pytest.mark.parametrize("field", TEAM_STAT_FIELDS)
def test_every_field_is_overridable(field: str) -> None:
    effective, manual = apply_manual_overrides(LOKO, {field: 77})
    assert manual == {field}
    assert getattr(effective, field) == 77
