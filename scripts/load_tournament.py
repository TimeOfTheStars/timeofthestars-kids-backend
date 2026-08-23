#!/usr/bin/env python3
"""Загрузка протоколов турнира в кабинет через админский API.

Читает JSON из scripts/tournament_data/ и заводит: игроков справочника, заявку
по командам, матчи и протоколы. Пишет через публичный HTTP API кабинета,
поэтому работает и с продом, и с локальной средой.

Идемпотентен: игроки ищутся по ФИО, турнир — по названию и дате, матчи — по
номеру. Повторный запуск не создаёт дублей, а досылает недостающее.

Запуск:
    export API_BASE=https://api.timeofthestars-kids.ru
    export ADMIN_USER=... ADMIN_PASSWORD=...      # или ADMIN_TOKEN=...
    python scripts/load_tournament.py scripts/tournament_data/letniy-kubok-2026-08-23.json --dry-run
    python scripts/load_tournament.py scripts/tournament_data/letniy-kubok-2026-08-23.json

Флаги:
    --dry-run   ничего не пишет, только показывает план
    --yes       не спрашивать подтверждение перед записью
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

TIMEOUT = 30.0


def normalize_team(name: str) -> str:
    """«ХК «ЗВЕЗДА»» → «звезда». Протоколы и база называют команды по-разному."""
    s = name.lower()
    s = re.sub(r"^хк\s*", "", s)
    s = s.strip(" «»\"'")
    return s.strip()


def normalize_person(name: str) -> str:
    """Для сопоставления ФИО: регистр и ё/е не должны создавать дубли игроков."""
    return re.sub(r"\s+", " ", name.strip().lower()).replace("ё", "е")


class Client:
    def __init__(self, base: str, token: str) -> None:
        self._c = httpx.Client(base_url=base.rstrip("/"), timeout=TIMEOUT)
        self._h = {"Authorization": f"Bearer {token}"}

    def get(self, path: str) -> Any:
        r = self._c.get(f"/api/admin{path}", headers=self._h)
        r.raise_for_status()
        return r.json()

    def public(self, path: str) -> Any:
        r = self._c.get(path)
        r.raise_for_status()
        return r.json()

    def send(self, method: str, path: str, body: Any) -> Any:
        r = self._c.request(method, f"/api/admin{path}", headers=self._h, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} → {r.status_code}: {r.text[:400]}")
        return r.json() if r.text else None

    def close(self) -> None:
        self._c.close()


def login(base: str) -> str:
    token = os.environ.get("ADMIN_TOKEN")
    if token:
        return token
    user, password = os.environ.get("ADMIN_USER"), os.environ.get("ADMIN_PASSWORD")
    if not user or not password:
        sys.exit("Нужны ADMIN_TOKEN или ADMIN_USER + ADMIN_PASSWORD в окружении")
    r = httpx.post(
        f"{base.rstrip('/')}/api/admin/auth/login",
        json={"username": user, "password": password},
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        sys.exit(f"Не удалось войти: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def validate(data: dict) -> list[str]:
    """Сверить данные до записи: счёт против таймлайна и номера против составов."""
    errors: list[str] = []
    rosters = {normalize_team(t): {n for n, _, _ in v} for t, v in data["rosters"].items()}

    for g in data["games"]:
        for side, team, score in (
            ("goals_a", g["team_a"], g["score_a"]),
            ("goals_b", g["team_b"], g["score_b"]),
        ):
            if len(g[side]) != score:
                errors.append(
                    f"М{g['match_no']} {team}: в таймлайне {len(g[side])} голов, в табло {score}"
                )
            known = rosters[normalize_team(team)]
            for i, (t, scorer, assists) in enumerate(g[side], start=1):
                if scorer not in known:
                    errors.append(
                        f"М{g['match_no']} {team}, строка {i} ({t}): автор №{scorer} не в составе"
                    )
                for a in assists:
                    if a not in known:
                        errors.append(
                            f"М{g['match_no']} {team}, строка {i} ({t}): передача №{a} не в составе"
                        )
    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_file", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    base = os.environ.get("API_BASE", "http://127.0.0.1:8000")
    data = json.loads(args.data_file.read_text())

    errors = validate(data)
    if errors:
        print("Данные не прошли проверку — записывать нельзя:\n")
        for e in errors:
            print("  ✗", e)
        sys.exit(1)
    print(f"Проверка данных пройдена: {len(data['games'])} матчей, "
          f"{sum(len(v) for v in data['rosters'].values())} игроков в составах.\n")

    token = login(base)
    c = Client(base, token)
    meta = data["tournament"]

    try:
        # --- турнир ---
        found = [
            t for t in c.get("/tournaments?limit=200")
            if t["title"].strip().lower() == meta["title"].strip().lower()
            and t["start_date"] == meta["date"]
        ]
        if len(found) != 1:
            sys.exit(
                f"Ожидался ровно один турнир «{meta['title']}» на {meta['date']}, найдено {len(found)}"
            )
        tournament = found[0]
        print(f"Турнир: {tournament['title']} ({tournament['start_date']}) — {tournament['id']}")

        team_by_name = {normalize_team(t["name"]): t for t in tournament["teams"]}
        missing_teams = [t for t in data["rosters"] if normalize_team(t) not in team_by_name]
        if missing_teams:
            sys.exit(
                "В турнире нет команд: " + ", ".join(missing_teams)
                + ". Команды турнира: " + ", ".join(t["name"] for t in tournament["teams"])
            )

        # --- регламент ---
        regulation = {
            "game_format": meta["game_format"],
            "period_minutes": meta["period_minutes"],
            "periods_count": meta["periods_count"],
        }
        need_regulation = {
            k: v for k, v in regulation.items() if tournament.get(k) != v
        }
        if need_regulation:
            print(f"  регламент: {need_regulation}")
            if not args.dry_run:
                c.send("PATCH", f"/tournaments/{tournament['id']}", need_regulation)

        # --- игроки справочника ---
        existing_players = c.get("/players?limit=1000")
        by_name = {normalize_person(p["full_name"]): p for p in existing_players}
        to_create = []
        for team, roster in data["rosters"].items():
            for number, full_name, position in roster:
                if normalize_person(full_name) not in by_name:
                    to_create.append((full_name, position))
                    by_name[normalize_person(full_name)] = {"__pending__": True}
        print(f"\nИгроки: в справочнике {len(existing_players)}, создать {len(to_create)}")
        if not args.dry_run:
            for full_name, position in to_create:
                body = {"full_name": full_name}
                if position:
                    body["position"] = position
                created = c.send("POST", "/players", body)
                by_name[normalize_person(full_name)] = created
                print(f"  + {full_name}" + (f" ({position})" if position else ""))

        # --- заявка ---
        roster_rows = c.get(f"/tournaments/{tournament['id']}/roster")
        already = {(r["team_id"], normalize_person(r["full_name"])) for r in roster_rows}
        print(f"\nЗаявка: уже заявлено {len(roster_rows)}")
        for team, roster in data["rosters"].items():
            tid = team_by_name[normalize_team(team)]["id"]
            batch = []
            for number, full_name, _pos in roster:
                if (tid, normalize_person(full_name)) in already:
                    continue
                pl = by_name[normalize_person(full_name)]
                batch.append({"player_id": pl.get("id"), "number": number, "_name": full_name})
            if not batch:
                print(f"  {team}: без изменений")
                continue
            print(f"  {team}: добавить {len(batch)}")
            if not args.dry_run:
                c.send(
                    "POST",
                    f"/tournaments/{tournament['id']}/roster",
                    {
                        "team_id": tid,
                        "players": [{"player_id": b["player_id"], "number": b["number"]} for b in batch],
                    },
                )

        if args.dry_run:
            print("\n--dry-run: матчи и протоколы не записаны "
                  "(им нужны id игроков, появляющиеся только при реальной записи).")
            return

        # --- матчи и протоколы ---
        roster_rows = c.get(f"/tournaments/{tournament['id']}/roster")
        # (team_id, номер) → player_id: именно так номера из бланка превращаются в игроков
        num_to_player = {
            (r["team_id"], r["number"]): r["player_id"] for r in roster_rows if r["number"] is not None
        }
        existing_games = {g["position"]: g for g in c.get(f"/tournaments/{tournament['id']}/games")}
        print(f"\nМатчи: уже заведено {len(existing_games)}")

        for g in data["games"]:
            a_id = team_by_name[normalize_team(g["team_a"])]["id"]
            b_id = team_by_name[normalize_team(g["team_b"])]["id"]
            payload = {
                "team_a_id": a_id,
                "team_b_id": b_id,
                "date": meta["date"],
                "score_a": g["score_a"],
                "score_b": g["score_b"],
                "shots_a": g["shots_a"],
                "shots_b": g["shots_b"],
                "position": g["match_no"],
            }
            game = existing_games.get(g["match_no"])
            if game is None:
                game = c.send("POST", f"/tournaments/{tournament['id']}/games", payload)
                action = "создан"
            else:
                game = c.send("PATCH", f"/games/{game['id']}", {
                    k: v for k, v in payload.items() if k != "position"
                })
                action = "обновлён"

            # Протокол: играли все заявленные, вратарь — по амплуа из данных.
            stat_lines, events = [], []
            for team, team_id, side in ((g["team_a"], a_id, "goals_a"), (g["team_b"], b_id, "goals_b")):
                for number, full_name, position in data["rosters"][team]:
                    pid = num_to_player.get((team_id, number))
                    if pid is None:
                        sys.exit(f"М{g['match_no']} {team}: №{number} ({full_name}) нет в заявке")
                    stat_lines.append({
                        "player_id": pid,
                        "team_id": team_id,
                        "is_goalie": position == "вратарь",
                    })
                for time_s, scorer, assists in g[side]:
                    ev = {
                        "team_id": team_id,
                        "period": 1,
                        "time": time_s,
                        "player_id": num_to_player[(team_id, scorer)],
                    }
                    if len(assists) > 0:
                        ev["assist1_player_id"] = num_to_player[(team_id, assists[0])]
                    if len(assists) > 1:
                        ev["assist2_player_id"] = num_to_player[(team_id, assists[1])]
                    events.append(ev)

            c.send("PUT", f"/games/{game['id']}/protocol", {
                "score_a": g["score_a"],
                "score_b": g["score_b"],
                "shots_a": g["shots_a"],
                "shots_b": g["shots_b"],
                "stat_lines": stat_lines,
                "events": events,
            })
            print(f"  М{g['match_no']} {g['team_a']} {g['score_a']}:{g['score_b']} {g['team_b']}"
                  f" — {action}, протокол записан ({len(events)} голов)")

        print("\nГотово. Таблица:")
        for row in c.public(f"/tournaments/{tournament['id']}/standings"):
            print(f"  {row['place']}. {row['team']['name']:<14} И{row['games']} "
                  f"В{row['wins']} Н{row['draws']} П{row['losses']} "
                  f"{row['goalsFor']}-{row['goalsAgainst']} ({row['goalDiff']:+d}) — {row['points']} очк.")
    finally:
        c.close()


if __name__ == "__main__":
    main()
