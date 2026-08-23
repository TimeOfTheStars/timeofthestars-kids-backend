"""Разбор игрового времени: формат бланка и терпимость к способам ввода."""

from __future__ import annotations

import pytest

from app.core.clock import ClockParseError, format_clock, parse_clock


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [
        # Ровно как на бланке.
        ("13:36", 13 * 60 + 36),
        ("00:02", 2),
        ("08:46", 8 * 60 + 46),
        ("14:15", 14 * 60 + 15),
        # Без двоеточия — секретарь набирает цифрами, JS нормализует на blur.
        ("1336", 13 * 60 + 36),
        ("816", 8 * 60 + 16),
        ("45", 45),
        # Пробелы и единицы.
        (" 07:19 ", 7 * 60 + 19),
        ("15м", 900),
        ("2м30с", 150),
        (985, 985),
    ],
)
def test_parse_clock_accepts(raw: str | int, seconds: int) -> None:
    assert parse_clock(raw) == seconds


@pytest.mark.parametrize("raw", ["", "   ", "abc", "13:70", None, "12:5x", -5])
def test_parse_clock_rejects(raw: object) -> None:
    with pytest.raises(ClockParseError):
        parse_clock(raw)  # type: ignore[arg-type]


def test_format_clock_roundtrip() -> None:
    assert format_clock(parse_clock("13:36")) == "13:36"
    assert format_clock(parse_clock("1336")) == "13:36"
    assert format_clock(2) == "00:02"


def test_format_clock_rejects_negative() -> None:
    with pytest.raises(ClockParseError):
        format_clock(-1)
