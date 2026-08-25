"""Админ-API статистики: справочник игроков, заявка на турнир, матчи, протокол."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import format_clock
from app.db.session import get_db_session
from app.deps import get_current_admin
from app.models.admin_user import AdminUser
from app.models.game import Game
from app.repositories import games as games_repo
from app.repositories import players as players_repo
from app.repositories import tournament_players as roster_repo
from app.repositories import tournaments as tournaments_repo
from app.schemas.game import (
    GameCreate,
    GameListItem,
    GameTeamItem,
    GameUpdate,
    ProtocolEventOut,
    ProtocolOut,
    ProtocolRequest,
    ProtocolStatLineOut,
)
from app.schemas.player import (
    PlayerCreate,
    PlayerListItem,
    PlayerUpdate,
    RosterAddRequest,
    RosterEntryItem,
    RosterEntryUpdate,
)
from app.services import games as games_service
from app.services.games import ProtocolValidationError
from app.services.stats import GameScore, goalie_totals_for_game

router = APIRouter(tags=["admin-stats"])


# ------------------------------------------------------- справочник игроков


@router.get("/players", response_model=list[PlayerListItem])
async def admin_list_players(
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> list[PlayerListItem]:
    rows = await players_repo.list_all(session, skip=skip, limit=limit, search=search)
    return [PlayerListItem.model_validate(r) for r in rows]


@router.post("/players", response_model=PlayerListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_player(
    body: PlayerCreate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlayerListItem:
    row = await players_repo.create_one(
        session,
        full_name=body.full_name,
        birth_date=body.birth_date,
        position=body.position,
        photo=body.photo,
    )
    return PlayerListItem.model_validate(row)


@router.patch("/players/{player_id}", response_model=PlayerListItem)
async def admin_update_player(
    player_id: uuid.UUID,
    body: PlayerUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlayerListItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет полей для обновления",
        )
    row = await players_repo.update_one(session, player_id, raw)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    return PlayerListItem.model_validate(row)


@router.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_player(
    player_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await players_repo.delete_one(session, player_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------- заявка на турнир


def _roster_item(entry) -> RosterEntryItem:  # noqa: ANN001 — entry: TournamentPlayer
    return RosterEntryItem(
        id=entry.id,
        team_id=entry.team_id,
        team_name=entry.team.name,
        player_id=entry.player_id,
        full_name=entry.player.full_name,
        birth_date=entry.player.birth_date,
        position=entry.player.position,
        photo=entry.player.photo,
        number=entry.number,
    )


async def _require_tournament(session: AsyncSession, tournament_id: uuid.UUID):  # noqa: ANN202
    row = await tournaments_repo.get_by_id(session, tournament_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Турнир не найден")
    return row


@router.get("/tournaments/{tournament_id}/roster", response_model=list[RosterEntryItem])
async def admin_list_roster(
    tournament_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RosterEntryItem]:
    await _require_tournament(session, tournament_id)
    return [_roster_item(e) for e in await roster_repo.list_for_tournament(session, tournament_id)]


@router.post(
    "/tournaments/{tournament_id}/roster",
    response_model=list[RosterEntryItem],
    status_code=status.HTTP_201_CREATED,
)
async def admin_add_to_roster(
    tournament_id: uuid.UUID,
    body: RosterAddRequest,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RosterEntryItem]:
    """Массово заявить игроков за команду. Уже заявленные молча пропускаются."""
    tournament = await _require_tournament(session, tournament_id)
    if body.team_id not in {link.team_id for link in tournament.team_links}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Команда не участвует в этом турнире",
        )
    if not body.players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не переданы игроки",
        )
    found = await players_repo.get_by_ids(session, [p.player_id for p in body.players])
    missing = {p.player_id for p in body.players} - {f.id for f in found}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не найдены игроки: {', '.join(str(m) for m in missing)}",
        )
    try:
        created = await roster_repo.add_many(
            session,
            tournament_id=tournament_id,
            team_id=body.team_id,
            entries=[(p.player_id, p.number) for p in body.players],
        )
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такой игровой номер в этой команде уже занят",
        ) from exc
    return [_roster_item(e) for e in created]


@router.patch(
    "/tournaments/{tournament_id}/roster/{entry_id}",
    response_model=RosterEntryItem,
)
async def admin_update_roster_entry(
    tournament_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: RosterEntryUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RosterEntryItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет полей для обновления",
        )
    existing = await roster_repo.get_by_id(session, entry_id)
    if existing is None or existing.tournament_id != tournament_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись заявки не найдена",
        )
    try:
        row = await roster_repo.update_one(session, entry_id, raw)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такой игровой номер в этой команде уже занят",
        ) from exc
    assert row is not None
    return _roster_item(row)


@router.delete(
    "/tournaments/{tournament_id}/roster/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_roster_entry(
    tournament_id: uuid.UUID,
    entry_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    existing = await roster_repo.get_by_id(session, entry_id)
    if existing is None or existing.tournament_id != tournament_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись заявки не найдена",
        )
    await roster_repo.delete_one(session, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------- матчи


def _game_item(game: Game) -> GameListItem:
    return GameListItem(
        id=game.id,
        tournament_id=game.tournament_id,
        position=game.position,
        team_a=GameTeamItem(
            id=game.team_a.id,
            name=game.team_a.name,
            city=game.team_a.city,
            logo=game.team_a.logo,
        ),
        team_b=GameTeamItem(
            id=game.team_b.id,
            name=game.team_b.name,
            city=game.team_b.city,
            logo=game.team_b.logo,
        ),
        score_a=game.score_a,
        score_b=game.score_b,
        shots_a=game.shots_a,
        shots_b=game.shots_b,
        date=game.date,
        time=game.time,
        video_url=game.video_url,
        scan=game.scan,
        is_finished=game.is_finished,
        created_at=game.created_at,
        updated_at=game.updated_at,
    )


@router.get("/tournaments/{tournament_id}/games", response_model=list[GameListItem])
async def admin_list_games(
    tournament_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[GameListItem]:
    await _require_tournament(session, tournament_id)
    return [_game_item(g) for g in await games_repo.list_for_tournament(session, tournament_id)]


@router.post(
    "/tournaments/{tournament_id}/games",
    response_model=GameListItem,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_game(
    tournament_id: uuid.UUID,
    body: GameCreate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GameListItem:
    tournament = await _require_tournament(session, tournament_id)
    tournament_team_ids = {link.team_id for link in tournament.team_links}
    for label, team_id in (("Команда 1", body.team_a_id), ("Команда 2", body.team_b_id)):
        if team_id not in tournament_team_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} не участвует в этом турнире",
            )

    fields = body.model_dump()
    if fields.get("position") is None:
        fields["position"] = await games_repo.next_position(session, tournament_id)
    fields["tournament_id"] = tournament_id
    # is_finished выводится, а не приходит от клиента.
    fields["is_finished"] = fields["score_a"] is not None and fields["score_b"] is not None
    row = await games_repo.create_one(session, fields=fields)
    return _game_item(row)


async def _require_game(session: AsyncSession, game_id: uuid.UUID) -> Game:
    game = await games_repo.get_by_id(session, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Матч не найден")
    return game


@router.get("/games/{game_id}", response_model=GameListItem)
async def admin_get_game(
    game_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GameListItem:
    return _game_item(await _require_game(session, game_id))


@router.patch("/games/{game_id}", response_model=GameListItem)
async def admin_update_game(
    game_id: uuid.UUID,
    body: GameUpdate,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GameListItem:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет полей для обновления",
        )
    game = await _require_game(session, game_id)

    new_a = raw.get("team_a_id", game.team_a_id)
    new_b = raw.get("team_b_id", game.team_b_id)
    if new_a == new_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Команда не может играть сама с собой",
        )
    # Проверяем факт СМЕНЫ команд, а не наличие полей в запросе: форма правки
    # присылает team_a_id/team_b_id всегда, и на присутствии ключа защита срабатывала
    # даже когда правят только скан или счёт.
    teams_changed = new_a != game.team_a_id or new_b != game.team_b_id
    if teams_changed:
        tournament = await _require_tournament(session, game.tournament_id)
        tournament_team_ids = {link.team_id for link in tournament.team_links}
        for label, team_id in (("Команда 1", new_a), ("Команда 2", new_b)):
            if team_id not in tournament_team_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{label} не участвует в этом турнире",
                )
        # Смена команды осиротила бы строки протокола и события прежних составов.
        if game.stat_lines or game.events:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "У матча уже заполнен протокол — сначала очистите составы и голы, "
                    "потом меняйте команды"
                ),
            )

    row = await games_repo.update_one(session, game_id, raw)
    assert row is not None
    return _game_item(row)


@router.delete("/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_game(
    game_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if not await games_repo.delete_one(session, game_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Матч не найден")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- протокол


async def _build_protocol(session: AsyncSession, game: Game) -> ProtocolOut:
    """Собрать протокол матча: составы с производными, таймлайн, сверка со счётом."""
    tournament = await _require_tournament(session, game.tournament_id)
    roster = {
        e.player_id: e
        for e in await roster_repo.list_for_tournament(session, game.tournament_id)
    }

    def number_of(player_id: uuid.UUID) -> int | None:
        entry = roster.get(player_id)
        return entry.number if entry else None

    def name_of(player_id: uuid.UUID) -> str:
        entry = roster.get(player_id)
        return entry.player.full_name if entry else str(player_id)

    # Вратарские считаются из табло и только когда вратарь у команды один.
    goalies_by_team: dict[uuid.UUID, list[uuid.UUID]] = {}
    for line in game.stat_lines:
        if line.is_goalie:
            goalies_by_team.setdefault(line.team_id, []).append(line.player_id)

    goalie_values: dict[uuid.UUID, tuple[int | None, int | None]] = {}
    ambiguous: list[uuid.UUID] = []
    if game.score_a is not None and game.score_b is not None:
        score = GameScore(
            team_a_id=game.team_a_id,
            team_b_id=game.team_b_id,
            score_a=game.score_a,
            score_b=game.score_b,
            shots_a=game.shots_a,
            shots_b=game.shots_b,
        )
        for team_id, ids in goalies_by_team.items():
            if len(ids) != 1:
                ambiguous.append(team_id)
                continue
            goalie_values[ids[0]] = goalie_totals_for_game(score, team_id)

    stat_lines = [
        ProtocolStatLineOut(
            player_id=line.player_id,
            team_id=line.team_id,
            full_name=line.player.full_name,
            number=number_of(line.player_id),
            position=line.player.position,
            is_goalie=line.is_goalie,
            goals=line.goals,
            assists=line.assists,
            points=line.goals + line.assists,
            goals_against=goalie_values.get(line.player_id, (None, None))[0],
            saves=goalie_values.get(line.player_id, (None, None))[1],
        )
        for line in game.stat_lines
    ]

    events = [
        ProtocolEventOut(
            id=ev.id,
            team_id=ev.team_id,
            period=ev.period,
            time=format_clock(ev.time_seconds),
            time_seconds=ev.time_seconds,
            sort_order=ev.sort_order,
            player_id=ev.player_id,
            player_name=name_of(ev.player_id),
            player_number=number_of(ev.player_id),
            assist1_player_id=ev.assist1_player_id,
            assist1_name=name_of(ev.assist1_player_id) if ev.assist1_player_id else None,
            assist1_number=number_of(ev.assist1_player_id) if ev.assist1_player_id else None,
            assist2_player_id=ev.assist2_player_id,
            assist2_name=name_of(ev.assist2_player_id) if ev.assist2_player_id else None,
            assist2_number=number_of(ev.assist2_player_id) if ev.assist2_player_id else None,
        )
        for ev in game.events
    ]

    timeline = games_service.goals_by_team(game.events)
    return ProtocolOut(
        game=_game_item(game),
        period_minutes=tournament.period_minutes,
        periods_count=tournament.periods_count,
        stat_lines=stat_lines,
        events=events,
        goals_in_timeline_a=timeline.get(game.team_a_id, 0),
        goals_in_timeline_b=timeline.get(game.team_b_id, 0),
        goalie_ambiguous_team_ids=ambiguous,
    )


@router.get("/games/{game_id}/protocol", response_model=ProtocolOut)
async def admin_get_protocol(
    game_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProtocolOut:
    return await _build_protocol(session, await _require_game(session, game_id))


@router.put("/games/{game_id}/protocol", response_model=ProtocolOut)
async def admin_save_protocol(
    game_id: uuid.UUID,
    body: ProtocolRequest,
    admin: Annotated[AdminUser, Depends(get_current_admin)],  # noqa: ARG001
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProtocolOut:
    """Полная замена протокола — единственный путь записи статистики."""
    try:
        game = await games_service.save_protocol(session, game_id, body)
    except ProtocolValidationError as exc:
        # get_db_session коммитит при нормальном возврате, поэтому частичную запись
        # нужно откатить явно, иначе она утечёт в БД.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Матч не найден")
    return await _build_protocol(session, game)
