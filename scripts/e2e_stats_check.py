"""End-to-end проверка статистики турниров на настоящем бумажном протоколе.

Гоняет полный цикл через ASGI (без поднятия сервера): арена → команды → турнир →
игроки → заявка → матч → протокол → все публичные ответы, и сверяет каждую цифру
с бланком «ПРОТОКОЛ ИГРЫ ПО ХОККЕЮ», турнир «Летний кубок», матч №1
ХК «ИСКРА» — ХК «ИМПУЛЬС» (табло 1:8, броски 8:26).

Требует ПУСТУЮ базу — скрипт пишет в неё данные и ничего за собой не убирает.
В pytest не включён сознательно: тому нужна живая Postgres, а unit-тесты в tests/
работают без инфраструктуры.

Запуск:
    createdb tots_e2e
    DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/tots_e2e \
    JWT_SECRET=any-long-enough-secret VK_TOKEN=dummy VK_SYNC_INTERVAL_MINUTES=0 \
    alembic upgrade head
    ... те же переменные ... python scripts/e2e_stats_check.py
"""
from __future__ import annotations

import asyncio

import httpx

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.admin_user import AdminUser

ADMIN_USER, ADMIN_PASS = "e2e_admin", "e2e-password-123"

# Составы ровно из бланка: (номер, ФИО, амплуа)
ISKRA_ROSTER = [
    (35, "Едигарев Роман", "вратарь"),
    (92, "Чубко Мирон", None), (18, "Королев Фёдор", None), (50, "Церус Арсений", None),
    (4, "Маслов Александр", None), (25, "Рассадин Давид", None), (7, "Разгуляев Даниил", None),
    (95, "Соколов Петр", None), (72, "Антипин Максим", None), (2, "Трофимов Мирон", None),
    (21, "Третьяков Егор", None), (97, "Ефименко Даниил", None), (11, "Степанов Артём", None),
]
IMPULS_ROSTER = [
    (1, "Малахов Дмитрий", "вратарь"),
    (13, "Рогов Савелий", None), (12, "Самыловский Егор", None), (11, "Кустов Артём", None),
    (10, "Гвоздев Никита", None), (9, "Аксёнтов Андрей", None), (8, "Голубев Дмитрий", None),
    (7, "Танин Антон", None), (6, "Семёнов Демид", None), (3, "Титов Герман", None),
    (2, "Пустовойтов Лев", None), (4, "Денисов Дмитрий", None), (5, "Лапшин Матвей", None),
]

# Таблицы «ВЗЯТИЕ ВОРОТ» как на бумаге: (время, № автора, [№ передач])
ISKRA_GOALS = [("00:02", 97, [])]
IMPULS_GOALS = [
    ("13:36", 12, [2]), ("12:36", 3, []), ("08:46", 13, [12]), ("07:19", 7, [11]),
    ("04:15", 13, []), ("14:15", 13, []), ("09:29", 13, [9]), ("08:42", 9, [12]),
]

ok_count = 0


def check(label: str, actual: object, expected: object) -> None:
    global ok_count
    if actual != expected:
        raise AssertionError(f"{label}: получено {actual!r}, ожидалось {expected!r}")
    ok_count += 1
    print(f"  ok  {label} = {actual!r}")


async def seed_admin() -> None:
    async with AsyncSessionLocal() as s:
        s.add(AdminUser(username=ADMIN_USER, password_hash=hash_password(ADMIN_PASS), role="admin"))
        await s.commit()


async def phase_paper_protocol() -> None:
    await seed_admin()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/admin/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        r.raise_for_status()
        H = {"Authorization": f"Bearer {r.json()['access_token']}"}

        print("\n--- 1. арена, команды, турнир ---")
        arena = (await c.post("/api/admin/arenas", headers=H, json={"name": "ГУОР по хоккею", "city": "Ярославль"})).json()
        iskra = (await c.post("/api/admin/teams", headers=H, json={"name": "ХК «ИСКРА»"})).json()
        impuls = (await c.post("/api/admin/teams", headers=H, json={"name": "ХК «ИМПУЛЬС»"})).json()
        r = await c.post("/api/admin/tournaments", headers=H, json={
            "title": "Летний кубок", "age_category": "2018-19", "birth_year": "2018-19",
            "start_date": "2026-08-23", "end_date": "2026-08-23", "arena_id": arena["id"],
            "game_format": "4-4", "period_minutes": 15, "periods_count": 3,
            "teams": [{"team_id": iskra["id"]}, {"team_id": impuls["id"]}],
        })
        assert r.status_code == 201, r.text
        T = r.json()
        check("регламент турнира", (T["game_format"], T["period_minutes"], T["periods_count"]), ("4-4", 15, 3))

        print("\n--- 2. игроки и заявка ---")
        num_to_id: dict[tuple[str, int], str] = {}
        for team, roster in (("iskra", ISKRA_ROSTER), ("impuls", IMPULS_ROSTER)):
            team_id = iskra["id"] if team == "iskra" else impuls["id"]
            entries = []
            for number, name, pos in roster:
                body = {"full_name": name}
                if pos:
                    body["position"] = pos
                pl = (await c.post("/api/admin/players", headers=H, json=body)).json()
                num_to_id[(team, number)] = pl["id"]
                entries.append({"player_id": pl["id"], "number": number})
            r = await c.post(f"/api/admin/tournaments/{T['id']}/roster", headers=H,
                             json={"team_id": team_id, "players": entries})
            assert r.status_code == 201, r.text
        roster_all = (await c.get(f"/api/admin/tournaments/{T['id']}/roster", headers=H)).json()
        check("в заявке игроков", len(roster_all), 26)

        print("\n--- 3. матч и табло ---")
        r = await c.post(f"/api/admin/tournaments/{T['id']}/games", headers=H, json={
            "team_a_id": iskra["id"], "team_b_id": impuls["id"], "date": "2026-08-23",
            "score_a": 1, "score_b": 8, "shots_a": 8, "shots_b": 26,
        })
        assert r.status_code == 201, r.text
        G = r.json()
        check("«МАТЧ №»", G["position"], 1)
        check("матч сыгран", G["is_finished"], True)

        print("\n--- 4. протокол: участие + таблицы «ВЗЯТИЕ ВОРОТ» ---")
        stat_lines = []
        for team, roster in (("iskra", ISKRA_ROSTER), ("impuls", IMPULS_ROSTER)):
            team_id = iskra["id"] if team == "iskra" else impuls["id"]
            for number, _name, pos in roster:
                stat_lines.append({
                    "player_id": num_to_id[(team, number)],
                    "team_id": team_id,
                    "is_goalie": pos == "вратарь",
                })
        events = []
        for team, table in (("iskra", ISKRA_GOALS), ("impuls", IMPULS_GOALS)):
            team_id = iskra["id"] if team == "iskra" else impuls["id"]
            for time_s, scorer, assists in table:
                ev = {"team_id": team_id, "period": 1, "time": time_s,
                      "player_id": num_to_id[(team, scorer)]}
                if len(assists) > 0:
                    ev["assist1_player_id"] = num_to_id[(team, assists[0])]
                if len(assists) > 1:
                    ev["assist2_player_id"] = num_to_id[(team, assists[1])]
                events.append(ev)

        r = await c.put(f"/api/admin/games/{G['id']}/protocol", headers=H, json={
            "score_a": 1, "score_b": 8, "shots_a": 8, "shots_b": 26,
            "stat_lines": stat_lines, "events": events,
        })
        assert r.status_code == 200, r.text
        P = r.json()
        check("голов в таймлайне ИСКРЫ", P["goals_in_timeline_a"], 1)
        check("голов в таймлайне ИМПУЛЬСА", P["goals_in_timeline_b"], 8)
        check("сходится со счётом", (P["goals_in_timeline_a"], P["goals_in_timeline_b"]),
              (P["game"]["score_a"], P["game"]["score_b"]))
        check("вратари распределены однозначно", P["goalie_ambiguous_team_ids"], [])

        lines = {sl["full_name"]: sl for sl in P["stat_lines"]}
        check("Едигарев ПШ/ОБ", (lines["Едигарев Роман"]["goals_against"], lines["Едигарев Роман"]["saves"]), (8, 18))
        check("Малахов ПШ/ОБ", (lines["Малахов Дмитрий"]["goals_against"], lines["Малахов Дмитрий"]["saves"]), (1, 7))
        check("Рогов №13 Г/П/О", (lines["Рогов Савелий"]["goals"], lines["Рогов Савелий"]["assists"], lines["Рогов Савелий"]["points"]), (4, 0, 4))
        check("Самыловский №12 Г/П/О", (lines["Самыловский Егор"]["goals"], lines["Самыловский Егор"]["assists"], lines["Самыловский Егор"]["points"]), (1, 2, 3))
        check("Ефименко №97 Г", lines["Ефименко Даниил"]["goals"], 1)
        check("порядок строк бланка сохранён", [e["sort_order"] for e in P["events"]], list(range(1, 10)))
        check("времена не пересортированы", [e["time"] for e in P["events"] if e["team_id"] == impuls["id"]],
              ["13:36", "12:36", "08:46", "07:19", "04:15", "14:15", "09:29", "08:42"])

        print("\n--- 5. публичный API ---")
        st = (await c.get(f"/tournaments/{T['id']}/standings")).json()
        check("таблица: 1 место", (st[0]["team"]["name"], st[0]["points"], st[0]["goalDiff"]), ("ХК «ИМПУЛЬС»", 2, 7))
        check("таблица: 2 место", (st[1]["team"]["name"], st[1]["points"], st[1]["goalDiff"]), ("ХК «ИСКРА»", 0, -7))

        best = (await c.get(f"/tournaments/{T['id']}/best-players?limit=3")).json()
        check("бомбардир №1", (best[0]["player"]["fullName"], best[0]["points"]), ("Рогов Савелий", 4))
        check("у бомбардира заполнена команда", best[0]["team"]["name"], "ХК «ИМПУЛЬС»")

        pl = (await c.get(f"/tournaments/{T['id']}/players")).json()
        check("игроков турнира", len(pl), 26)
        rogov = next(p for p in pl if p["player"]["fullName"] == "Рогов Савелий")
        check("Рогов в списке турнира", (rogov["games"], rogov["goals"], rogov["points"], rogov["number"]), (1, 4, 4, 13))
        edig = next(p for p in pl if p["player"]["fullName"] == "Едигарев Роман")
        check("Едигарев вратарь", (edig["isGoalie"], edig["goalsAgainst"], edig["saves"], edig["minutesPlayed"]), (True, 8, 18, 45))

        career = (await c.get(f"/players/{num_to_id[('impuls', 13)]}/stats")).json()
        check("карьера Рогова", (career["career"]["games"], career["career"]["goals"], career["career"]["points"]), (1, 4, 4))
        check("у полевого в карьере вратарских нет",
              (career["career"]["goalsAgainst"], career["career"]["saves"]), (None, None))
        # Карточка вратаря обязана показывать ПШ/ОБ — иначе она пустая.
        gk_career = (await c.get(f"/players/{num_to_id[('iskra', 35)]}/stats")).json()
        check("карьера вратаря Едигарева",
              (gk_career["career"]["goalsAgainst"], gk_career["career"]["saves"], gk_career["career"]["minutesPlayed"]),
              (8, 18, 45))
        check("вратарские в разбивке по турниру",
              gk_career["byTournament"][0]["totals"]["saves"], 18)
        check("вратарские в разбивке по команде",
              gk_career["byTeam"][0]["totals"]["goalsAgainst"], 8)
        check("разбивка по турниру", (career["byTournament"][0]["name"], career["byTournament"][0]["totals"]["goals"]), ("Летний кубок", 4))
        check("разбивка по команде", (career["byTeam"][0]["name"], career["byTeam"][0]["totals"]["goals"]), ("ХК «ИМПУЛЬС»", 4))

        games = (await c.get(f"/tournaments/{T['id']}/games")).json()
        check("матчей в турнире", len(games), 1)
        check("табло в публичном API", (games[0]["scoreA"], games[0]["scoreB"], games[0]["shotsA"], games[0]["shotsB"]), (1, 8, 8, 26))

        gp = (await c.get(f"/games/{G['id']}")).json()
        check("состав ИСКРЫ в матче", len(gp["rosterA"]), 13)
        check("вратарь первым в составе", gp["rosterA"][0]["player"]["fullName"], "Едигарев Роман")
        # Вратарские ЭТОГО матча должны приходить в протоколе, а не только в итогах турнира.
        gk_a = gp["rosterA"][0]
        check("ПШ/ОБ вратаря в протоколе матча", (gk_a["goalsAgainst"], gk_a["saves"]), (8, 18))
        gk_b = next(x for x in gp["rosterB"] if x["isGoalie"])
        check("ПШ/ОБ вратаря соперника", (gk_b["goalsAgainst"], gk_b["saves"]), (1, 7))
        field_player = next(x for x in gp["rosterA"] if not x["isGoalie"])
        check("у полевого вратарских нет", (field_player["goalsAgainst"], field_player["saves"]), (None, None))
        check("голов в хронологии", len(gp["goals"]), 9)
        first_impuls = next(g for g in gp["goals"] if g["teamId"] == impuls["id"])
        check("первый гол ИМПУЛЬСА", (first_impuls["time"], first_impuls["scorerNumber"], first_impuls["assistNumbers"]), ("13:36", 12, [2]))

        tours = (await c.get("/tournaments")).json()
        t_pub = next(t for t in tours if t["id"] == T["id"])
        check("hasStats", t_pub["hasStats"], True)
        check("регламент в публичном API", (t_pub["gameFormat"], t_pub["periodMinutes"], t_pub["periodsCount"]), ("4-4", 15, 3))




async def phase_guards() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/admin/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        H = {"Authorization": f"Bearer {r.json()['access_token']}"}

        T = (await c.get("/api/admin/tournaments", headers=H)).json()[0]
        teams = T["teams"]
        iskra = next(t for t in teams if "ИСКРА" in t["name"])
        impuls = next(t for t in teams if "ИМПУЛЬС" in t["name"])
        roster_before = (await c.get(f"/api/admin/tournaments/{T['id']}/roster", headers=H)).json()
        games_before = (await c.get(f"/api/admin/tournaments/{T['id']}/games", headers=H)).json()

        print("\n--- 1. РЕГРЕССИЯ: сохранение турнира без изменений не сносит данные ---")
        r = await c.patch(f"/api/admin/tournaments/{T['id']}", headers=H, json={
            "teams": [{"team_id": iskra["id"]}, {"team_id": impuls["id"]}],
        })
        check("PATCH турнира прошёл", r.status_code, 200)
        roster_after = (await c.get(f"/api/admin/tournaments/{T['id']}/roster", headers=H)).json()
        games_after = (await c.get(f"/api/admin/tournaments/{T['id']}/games", headers=H)).json()
        check("заявка на месте", len(roster_after), len(roster_before))
        check("матчи на месте", len(games_after), len(games_before))
        check("id записей заявки не пересозданы",
              {e["id"] for e in roster_after}, {e["id"] for e in roster_before})

        print("\n--- 2. нельзя убрать команду, у которой есть матчи ---")
        r = await c.patch(f"/api/admin/tournaments/{T['id']}", headers=H,
                          json={"teams": [{"team_id": iskra["id"]}]})
        check("статус", r.status_code, 409)
        check("в тексте названа команда", "ИМПУЛЬС" in r.json()["detail"], True)
        check("данные не тронуты",
              len((await c.get(f"/api/admin/tournaments/{T['id']}/roster", headers=H)).json()), 26)

        print("\n--- 3. смена порядка/фото команд по-прежнему работает ---")
        r = await c.patch(f"/api/admin/tournaments/{T['id']}", headers=H, json={
            "teams": [{"team_id": impuls["id"], "photo": "/static/team-photos/x.jpg"},
                      {"team_id": iskra["id"]}],
        })
        check("статус", r.status_code, 200)
        check("порядок применён", [t["name"] for t in r.json()["teams"]],
              ["ХК «ИМПУЛЬС»", "ХК «ИСКРА»"])
        check("фото применено", r.json()["teams"][0]["photo"], "/static/team-photos/x.jpg")

        G = games_after[0]
        print("\n--- 4. валидация протокола ---")
        # 4a. незаявленный игрок
        extra = (await c.post("/api/admin/players", headers=H,
                              json={"full_name": "Посторонний Игрок"})).json()
        r = await c.put(f"/api/admin/games/{G['id']}/protocol", headers=H, json={
            "score_a": 1, "score_b": 8,
            "stat_lines": [{"player_id": extra["id"], "team_id": iskra["id"]}],
        })
        check("незаявленный игрок отклонён", r.status_code, 422)
        check("текст про заявку", "не заявлен" in r.json()["detail"], True)

        # 4b. время больше длительности периода (15 мин)
        line = (await c.get(f"/api/admin/games/{G['id']}/protocol", headers=H)).json()["stat_lines"][0]
        r = await c.put(f"/api/admin/games/{G['id']}/protocol", headers=H, json={
            "score_a": 1, "score_b": 8,
            "stat_lines": [{"player_id": line["player_id"], "team_id": line["team_id"]}],
            "events": [{"team_id": line["team_id"], "period": 1, "time": "16:00",
                        "player_id": line["player_id"]}],
        })
        check("время больше периода отклонено", r.status_code, 422)
        check("текст про длительность", "длительности периода" in r.json()["detail"], True)

        # 4c. период больше регламента (3 + овертайм = 4)
        r = await c.put(f"/api/admin/games/{G['id']}/protocol", headers=H, json={
            "score_a": 1, "score_b": 8,
            "stat_lines": [{"player_id": line["player_id"], "team_id": line["team_id"]}],
            "events": [{"team_id": line["team_id"], "period": 5, "time": "01:00",
                        "player_id": line["player_id"]}],
        })
        check("период больше регламента отклонён", r.status_code, 422)

        # 4d. автор гола без строки участия
        r = await c.put(f"/api/admin/games/{G['id']}/protocol", headers=H, json={
            "score_a": 1, "score_b": 8,
            "stat_lines": [{"player_id": line["player_id"], "team_id": line["team_id"]}],
            "events": [{"team_id": line["team_id"], "period": 1, "time": "01:00",
                        "player_id": extra["id"]}],
        })
        check("автор без участия отклонён", r.status_code, 422)

        print("\n--- 5. протокол не повреждён после отказов ---")
        P = (await c.get(f"/api/admin/games/{G['id']}/protocol", headers=H)).json()
        check("строк участия", len(P["stat_lines"]), 26)
        check("голов в таймлайне", len(P["events"]), 9)

        print("\n--- 6. незаигравший в заявке приходит с нулями ---")
        r = await c.post(f"/api/admin/tournaments/{T['id']}/roster", headers=H, json={
            "team_id": iskra["id"], "players": [{"player_id": extra["id"], "number": 77}]})
        check("добавлен в заявку", r.status_code, 201)
        pl = (await c.get(f"/tournaments/{T['id']}/players")).json()
        bench = next(p for p in pl if p["player"]["fullName"] == "Посторонний Игрок")
        check("присутствует с нулями", (bench["games"], bench["goals"], bench["points"]), (0, 0, 0))
        check("всего в списке", len(pl), 27)
        best = (await c.get(f"/tournaments/{T['id']}/best-players?limit=50")).json()
        check("в бомбардиры не попал",
              any(p["player"]["fullName"] == "Посторонний Игрок" for p in best), False)

        print("\n--- 7. занятый игровой номер ---")
        dup = (await c.post("/api/admin/players", headers=H, json={"full_name": "Дубль Номера"})).json()
        r = await c.post(f"/api/admin/tournaments/{T['id']}/roster", headers=H, json={
            "team_id": iskra["id"], "players": [{"player_id": dup["id"], "number": 77}]})
        check("дубль номера отклонён", r.status_code, 409)
        check("текст про номер", "номер" in r.json()["detail"].lower(), True)

        print("\n--- 8. контракт events: None не трогает таймлайн, [] очищает ---")
        lines = [{"player_id": sl["player_id"], "team_id": sl["team_id"], "is_goalie": sl["is_goalie"]}
                 for sl in P["stat_lines"]]
        r = await c.put(f"/api/admin/games/{G['id']}/protocol", headers=H,
                        json={"score_a": 1, "score_b": 8, "shots_a": 8, "shots_b": 26,
                              "stat_lines": lines})
        check("events не передан — статус", r.status_code, 200)
        check("таймлайн сохранён", len(r.json()["events"]), 9)
        check("производные пересчитаны",
              next(sl["goals"] for sl in r.json()["stat_lines"] if sl["full_name"] == "Рогов Савелий"), 4)

        r = await c.put(f"/api/admin/games/{G['id']}/protocol", headers=H,
                        json={"score_a": 1, "score_b": 8, "stat_lines": lines, "events": []})
        check("events=[] — статус", r.status_code, 200)
        check("таймлайн очищен", len(r.json()["events"]), 0)
        check("производные обнулены", {sl["goals"] for sl in r.json()["stat_lines"]}, {0})
        check("расхождение со счётом видно",
              (r.json()["goals_in_timeline_a"], r.json()["goals_in_timeline_b"]), (0, 0))

        print("\n--- 9. защита от смены команд у заполненного матча ---")
        r = await c.patch(f"/api/admin/games/{G['id']}", headers=H,
                          json={"team_a_id": impuls["id"], "team_b_id": iskra["id"]})
        check("смена команд отклонена", r.status_code, 409)

        print("\n--- 10. скан правится у матча с заполненным протоколом ---")
        # Форма правки всегда присылает team_a_id/team_b_id. Защита обязана смотреть
        # на факт СМЕНЫ команд, иначе правка одного скана упирается в 409.
        r = await c.patch(f"/api/admin/games/{G['id']}", headers=H, json={
            "team_a_id": iskra["id"], "team_b_id": impuls["id"],
            "scan": "/static/protocols/исправленный.pdf"})
        check("правка скана прошла", r.status_code, 200)
        check("скан записан", r.json()["scan"], "/static/protocols/исправленный.pdf")
        r = await c.patch(f"/api/admin/games/{G['id']}", headers=H, json={"scan": None})
        check("скан снимается", (r.status_code, r.json()["scan"]), (200, None))
        pr = (await c.get(f"/api/admin/games/{G['id']}/protocol", headers=H)).json()
        check("протокол не пострадал", len(pr["stat_lines"]), 26)





async def main() -> None:
    print("=" * 70)
    print("ФАЗА 1: бумажный протокол «Летний кубок», матч №1")
    print("=" * 70)
    await phase_paper_protocol()
    print()
    print("=" * 70)
    print("ФАЗА 2: регрессии и защитные проверки")
    print("=" * 70)
    await phase_guards()
    print(f"\n✅ ВСЁ СОШЛОСЬ: {ok_count} проверок")


asyncio.run(main())
