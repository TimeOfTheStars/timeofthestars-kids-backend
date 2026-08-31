"""Матчи и сохранение протокола — единственный путь записи статистики.

Алгоритм полной замены унаследован из timeofthestars-backend-v2
(app/services/game_service.py:save_protocol): голы и передачи никогда не приходят
от клиента, они выводятся из таймлайна, поэтому цифры не могут разойтись с событиями.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import parse_clock
from app.models.game import Game, GameEvent, GamePlayerStat
from app.models.tournament import Tournament
from app.repositories import games as games_repo
from app.repositories import tournament_players as roster_repo
from app.schemas.game import GameEventIn, ProtocolRequest
from app.services.stats import derive_totals

# Последний допустимый период — овертайм сверх регламента.
_OVERTIME_ALLOWANCE = 1


class ProtocolValidationError(ValueError):
    """Протокол не прошёл проверку. Роут превращает это в 422 с текстом для секретаря."""


@dataclass(frozen=True)
class _Regulation:
    """Регламент турнира, нужный для проверки времени и периода."""

    period_minutes: int | None
    periods_count: int | None

    @property
    def max_time_seconds(self) -> int | None:
        return self.period_minutes * 60 if self.period_minutes else None

    @property
    def max_period(self) -> int | None:
        return self.periods_count + _OVERTIME_ALLOWANCE if self.periods_count else None


async def _regulation(session: AsyncSession, tournament_id: uuid.UUID) -> _Regulation:
    stmt = select(Tournament.period_minutes, Tournament.periods_count).where(
        Tournament.id == tournament_id,
    )
    row = (await session.execute(stmt)).one_or_none()
    return _Regulation(row[0], row[1]) if row else _Regulation(None, None)


def _validate_stat_lines(
    body: ProtocolRequest,
    game: Game,
    roster: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """Строки участия: команда матча, без дублей, только заявленные игроки."""
    match_teams = {game.team_a_id, game.team_b_id}
    seen: set[uuid.UUID] = set()

    for line in body.stat_lines:
        if line.team_id not in match_teams:
            msg = f"Команда {line.team_id} не участвует в этом матче"
            raise ProtocolValidationError(msg)
        if line.player_id in seen:
            msg = f"Игрок {line.player_id} указан в протоколе дважды"
            raise ProtocolValidationError(msg)
        seen.add(line.player_id)
        if (line.player_id, line.team_id) not in roster:
            msg = (
                f"Игрок {line.player_id} не заявлен за эту команду на турнире — "
                "сначала добавьте его в состав"
            )
            raise ProtocolValidationError(msg)


def _validate_events(
    events: list,  # noqa: ANN001 — GameEventIn или ORM GameEvent
    game: Game,
    participation: set[tuple[uuid.UUID, uuid.UUID]],
    regulation: _Regulation,
) -> None:
    """События проверяются против ИТОГОВОГО набора участников.

    Важно: сюда попадают и события, уже лежащие в БД (когда events не переданы) —
    иначе переписанные составы могли бы оставить событие с игроком без строки участия.
    """
    match_teams = {game.team_a_id, game.team_b_id}

    for idx, ev in enumerate(events, start=1):
        if ev.team_id not in match_teams:
            msg = f"Гол №{idx}: команда не участвует в этом матче"
            raise ProtocolValidationError(msg)

        if regulation.max_period is not None and ev.period > regulation.max_period:
            msg = (
                f"Гол №{idx}: период {ev.period} больше регламента турнира "
                f"({regulation.periods_count} + овертайм)"
            )
            raise ProtocolValidationError(msg)

        seconds = ev.time_seconds
        max_seconds = regulation.max_time_seconds
        if max_seconds is not None and seconds > max_seconds:
            msg = (
                f"Гол №{idx}: время больше длительности периода "
                f"({regulation.period_minutes} мин)"
            )
            raise ProtocolValidationError(msg)

        # Автор и ассистенты обязаны иметь строку участия ЗА ТУ ЖЕ команду.
        for role, pid in [("Автор", ev.player_id), *[("Ассистент", a) for a in ev.assist_ids]]:
            if (pid, ev.team_id) not in participation:
                msg = (
                    f"Гол №{idx}: {role.lower()} {pid} не отмечен как игравший "
                    "за эту команду в этом матче"
                )
                raise ProtocolValidationError(msg)


def _assign_sort_order(events: list[GameEventIn]) -> list[tuple[int, GameEventIn]]:
    """sort_order внутри периода = порядок строк, присланный клиентом.

    На бланке порядок задаёт колонка «№», а времена не отсортированы (13:36, 12:36,
    08:46, …), поэтому сортировать по времени нельзя — сохраняем порядок бланка.
    Клиент sort_order не присылает: его всегда проставляет сервер.
    """
    counters: dict[int, int] = {}
    out: list[tuple[int, GameEventIn]] = []
    for ev in events:
        counters[ev.period] = counters.get(ev.period, 0) + 1
        out.append((counters[ev.period], ev))
    return out


async def save_protocol(
    session: AsyncSession,
    game_id: uuid.UUID,
    body: ProtocolRequest,
) -> Game | None:
    """Полная замена протокола матча. Возвращает None, если матча нет.

    Контракт events: None — таймлайн не трогаем (но перепроверяем против новых
    составов и пересчитываем производные), [] — очищаем, список — полная замена.
    """
    game = await games_repo.get_by_id(session, game_id)
    if game is None:
        return None

    regulation = await _regulation(session, game.tournament_id)
    roster = await roster_repo.registered_pairs(session, game.tournament_id)

    _validate_stat_lines(body, game, roster)

    # Табло. is_finished выводится, клиент его не присылает.
    for attr in ("score_a", "score_b", "shots_a", "shots_b"):
        setattr(game, attr, getattr(body, attr))
    game.is_finished = game.score_a is not None and game.score_b is not None

    stored_events = list(game.events)

    # Итоговый набор участников — по нему валидируются события.
    participation = {(line.player_id, line.team_id) for line in body.stat_lines}

    if body.events is None:
        # Таймлайн остаётся в БД: проверяем уцелевшие события против новых составов.
        _validate_events(stored_events, game, participation, regulation)
        effective_for_totals: list = stored_events
    else:
        _validate_events(body.events, game, participation, regulation)
        effective_for_totals = list(body.events)

    # Удаляем старые строки участия и (если таймлайн заменяется) события,
    # затем flush: без него uq_game_player не даст вставить новые строки поверх старых.
    await session.execute(delete(GamePlayerStat).where(GamePlayerStat.game_id == game.id))
    if body.events is not None:
        await session.execute(delete(GameEvent).where(GameEvent.game_id == game.id))
    await session.flush()

    totals = derive_totals(effective_for_totals)
    for line in body.stat_lines:
        t = totals.get(line.player_id, {"goals": 0, "assists": 0})
        session.add(
            GamePlayerStat(
                game_id=game.id,
                player_id=line.player_id,
                team_id=line.team_id,
                is_goalie=line.is_goalie,
                minutes_played=line.minutes_played,
                goals=t["goals"],
                assists=t["assists"],
            ),
        )

    if body.events is not None:
        for sort_order, ev in _assign_sort_order(body.events):
            session.add(
                GameEvent(
                    game_id=game.id,
                    team_id=ev.team_id,
                    type="goal",
                    period=ev.period,
                    time_seconds=parse_clock(ev.time),
                    sort_order=sort_order,
                    player_id=ev.player_id,
                    assist1_player_id=ev.assist1_player_id,
                    assist2_player_id=ev.assist2_player_id,
                ),
            )

    await session.commit()
    return await games_repo.get_by_id(session, game_id)


def goals_by_team(events: list) -> dict[uuid.UUID, int]:  # noqa: ANN001
    """Сколько голов в таймлайне у каждой команды — для сверки со счётом."""
    out: dict[uuid.UUID, int] = {}
    for ev in events:
        out[ev.team_id] = out.get(ev.team_id, 0) + 1
    return out
