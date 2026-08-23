"""Разбор и форматирование игрового времени в формате бумажного протокола (MM:SS).

Единственное место в проекте, где парсится время события. Секретарь вбивает время
так же, как оно записано на бланке: «13:36». Терпим к частым способам ввода —
без двоеточия («1336»), с русскими «м»/«с», с лишними пробелами.
"""

from __future__ import annotations

import re

__all__ = ["ClockParseError", "format_clock", "parse_clock"]


class ClockParseError(ValueError):
    """Время не распознано."""


_COLON = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})$")
_UNITS = re.compile(r"^(?:(\d{1,3})\s*[мm])?\s*(?:(\d{1,2})\s*[сs])?$")


def parse_clock(raw: str | int | None) -> int:
    """Строку игрового времени → секунды.

    Принимает: `13:36`, `1:05:30`, `1336` (→ 13:36), `816` (→ 8:16), `45` (→ 45 секунд),
    `15м`, `2м30с`. Пустая строка и мусор дают ClockParseError.
    """
    if raw is None:
        msg = "Пустое время"
        raise ClockParseError(msg)
    if isinstance(raw, int):
        if raw < 0:
            msg = f"Отрицательное время: {raw}"
            raise ClockParseError(msg)
        return raw

    s = str(raw).strip().replace(" ", "")
    if not s:
        msg = "Пустое время"
        raise ClockParseError(msg)

    m = _COLON.match(s)
    if m:
        hours, minutes, seconds = m.group(1), m.group(2), m.group(3)
        total = int(minutes) * 60 + int(seconds)
        if hours:
            total += int(hours) * 3600
        if int(seconds) >= 60:  # noqa: PLR2004 — 60 секунд в минуте
            msg = f"Секунд больше 59: {raw}"
            raise ClockParseError(msg)
        return total

    if s.isdigit():
        # «1336» → 13:36, «816» → 8:16, «45» → 45 секунд.
        # Логика бланка: последние две цифры — секунды, если число длиннее двух знаков.
        if len(s) <= 2:  # noqa: PLR2004 — «45» это просто секунды
            return int(s)
        minutes, seconds = int(s[:-2]), int(s[-2:])
        if seconds >= 60:  # noqa: PLR2004
            msg = f"Секунд больше 59: {raw}"
            raise ClockParseError(msg)
        return minutes * 60 + seconds

    m = _UNITS.match(s.lower())
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)

    msg = f"Не удалось разобрать время: {raw!r}"
    raise ClockParseError(msg)


def format_clock(seconds: int) -> str:
    """Секунды → `MM:SS` (как на бланке). Часы не выделяем — период короткий."""
    if seconds < 0:
        msg = f"Отрицательное время: {seconds}"
        raise ClockParseError(msg)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
