# Публичное API

Без авторизации. Всё, что читает и отправляет сайт. Ответы читающих ручек приходят с
`Cache-Control: public, max-age=300`. Поля — **camelCase**.

Про то, как получаются цифры статистики, — отдельный документ: [statistics.md](statistics.md).

## Оглавление

**Контент**
- [`GET /tournaments`](#get-tournaments) — турниры
- [`GET /reviews`](#get-reviews) — отзывы
- [`GET /news`](#get-news) — новости

**Статистика**
- [`GET /tournaments/{id}/standings`](#get-tournamentsidstandings) — таблица турнира
- [`GET /tournaments/{id}/games`](#get-tournamentsidgames) — матчи турнира
- [`GET /games/{id}`](#get-gamesid) — матч с протоколом
- [`GET /tournaments/{id}/players`](#get-tournamentsidplayers) — игроки турнира
- [`GET /tournaments/{id}/best-players`](#get-tournamentsidbest-players) — бомбардиры
- [`GET /players/{id}/stats`](#get-playersidstats) — карточка игрока
- [`GET /teams`](#get-teams) · [`GET /teams/{id}`](#get-teamsid) — команды

**Формы с сайта**
- [`POST /appointments`](#post-appointments) — запись на тренировку
- [`POST /service-requests`](#post-service-requests) — заявка на услугу
- [`POST /questions`](#post-questions) — вопрос
- [`POST /tournament-applications/player`](#post-tournament-applicationsplayer) — заявка игрока
- [`POST /tournament-applications/team`](#post-tournament-applicationsteam) — заявка команды

- [Сервисные ручки](#сервисные-ручки) — `GET /health`, `GET /`

> Скрытый турнир (`is_visible = false`) отдаёт `404` во **всех** ручках статистики по нему,
> а не пустой массив.

---

## GET /tournaments

Массив турниров. Отсортирован сервером.

```bash
curl -s https://api.timeofthestars-kids.ru/tournaments
```

```jsonc
{
  "id": "95f35be3-5fd1-4cd4-bc37-424a89bc2f3d",
  "title": "Летний Кубок",
  "ageCategory": "U8|U7",
  "birthYear": "2018-19",
  "startDate": "2026-08-23",
  "endDate": "2026-08-23",
  "startTime": "13:00",
  "endTime": "15:00",
  "arena": {
    "name": "ГЛА ГУОР",
    "url": null,
    "address": null,
    "city": "Ярославль"
  },
  "season": "2026/2027",
  "description": "Регулярный турнир по хоккею с шайбой «ЛЕТНИЙ КУБОК»…",
  "url": "https://vk.ru/wall-125696800_1829",
  "recordingsUrl": "https://vkvideo.ru/playlist/-125696800_32",
  "gameFormat": "4-4",
  "periodMinutes": 15,
  "periodsCount": 2,
  "hasGames": true,
  "teams": [
    { "name": "Звезда", "city": null, "logo": "https://…/static/teams/….png", "photo": null }
  ]
}
```

| Поле | Прим. |
|---|---|
| `gameFormat` | Формат игры из шапки протокола, например `"4-4"` |
| `periodMinutes` / `periodsCount` | Регламент. Из них считаются минуты в воротах |
| `hasGames` | Заведён ли хотя бы один матч — **неважно, сыгран ли он**. **Начинайте отсюда**: у большинства турниров матчей в системе нет, и лишние запросы делать не нужно |
| `season` | Если не задан админом, выводится из даты начала (август–декабрь → `YYYY/YYYY+1`) |
| `teams[].photo` | Общее фото состава именно на этом турнире |

**Про `hasGames`.** Флаг становится `true`, как только матчи созданы, — чтобы турнир можно
было открыть и показать расписание ещё до первых результатов. Он **не** означает, что
матчи сыграны: это смотрится по `isFinished` каждого матча в `/tournaments/{id}/games`.
У несыгранного матча `scoreA`/`scoreB` равны `null`, а таблица при этом отдаёт все заявленные
команды с нулями — её можно показывать сразу.

> ⚠️ В `teams[]` **нет `id`** — это исторический формат, он не менялся. Идентификаторы команд
> приходят в ручках статистики ниже и в `GET /teams`.

---

## GET /tournaments/{id}/standings

Таблица турнира. **Уже отсортирована** — место равно `place`, оно же индекс + 1.
Не пересортировывайте: порядок задаёт цепочка `очки → разница шайб → забитые шайбы → название`.

Очки: **победа 2, ничья 1, поражение 0**. Дополнительного времени и буллитов в схеме нет.
В таблицу идут все матчи с заполненным счётом — стадий и плей-офф не существует.

```json
[
  {
    "place": 1,
    "team": { "id": "3f6c3db1-…", "name": "Звезда", "city": null, "logo": "https://…" },
    "games": 3, "wins": 3, "draws": 0, "losses": 0,
    "goalsFor": 22, "goalsAgainst": 8, "goalDiff": 14, "points": 6
  }
]
```

Заявленная, но ещё не игравшая команда **присутствует с нулями**. При равных очках она
окажется выше проигравшей с отрицательной разницей — следствие цепочки tie-break, не ошибка.

---

## GET /tournaments/{id}/games

Календарь и результаты в порядке «МАТЧ №».

```json
[
  {
    "id": "0ac3a154-…",
    "matchNo": 1,
    "date": "2026-08-23",
    "time": null,
    "teamA": { "id": "ffbcfc25-…", "name": "Искра",   "city": null, "logo": "https://…" },
    "teamB": { "id": "3f6c3db1-…", "name": "Импульс", "city": null, "logo": "https://…" },
    "scoreA": 1, "scoreB": 8,
    "shotsA": 8, "shotsB": 26,
    "videoUrl": null,
    "scan": "https://…/static/protocols/….pdf",
    "isFinished": true
  }
]
```

| Поле | Прим. |
|---|---|
| `matchNo` | Номер матча в турнире, он же порядок сортировки |
| `scoreA` / `scoreB` | «Голы» из табло. `null` у ещё не сыгранного матча |
| `shotsA` / `shotsB` | «Броски» из табло. Из них выводится вратарская статистика |
| `scan` | Скан бумажного протокола — картинка или PDF, `null` если не приложен |
| `isFinished` | `true`, когда заполнены **оба** счёта. Ставит сервер |

---

## GET /games/{id}

Матч с протоколом: составы обеих команд и хронология голов. Данные для страницы матча.

```jsonc
{
  "game": { /* тот же объект, что в /tournaments/{id}/games */ },

  "rosterA": [
    {
      "player": {
        "id": "82461ace-…",
        "fullName": "Едигарев Роман",
        "photo": null,
        "position": "вратарь",
        "birthDate": null
      },
      "team": { "id": "ffbcfc25-…", "name": "Искра", "city": null, "logo": "https://…" },
      "number": 35,
      "games": 1,
      "goals": 0, "assists": 0, "points": 0,
      "isGoalie": true,
      "goalsAgainst": 8,      // пропущено в ЭТОМ матче
      "saves": 18,            // отражено = броски соперника − его голы
      "minutesPlayed": 30
    }
  ],
  "rosterB": [ /* то же для второй команды */ ],

  "goals": [
    {
      "period": 1,
      "time": "13:36",
      "teamId": "3f6c3db1-…",
      "scorer": { "id": "37bcbe3a-…", "fullName": "Самыловский Егор", "photo": null, "position": null, "birthDate": null },
      "scorerNumber": 12,
      "assists": [ { "id": "82b753ab-…", "fullName": "Пустовойтов Лев", "photo": null, "position": null, "birthDate": null } ],
      "assistNumbers": [2]
    }
  ]
}
```

**Состав — те, кто реально играл**, а не вся заявка на турнир. Порядок как в бумажном
бланке: сначала вратари, потом остальные по возрастанию номера. `games` в строке состава
всегда `1` — это статистика одного матча.

**`goals` — единый массив на обе команды**, уже в правильном порядке; команда определяется
по `teamId`. Нужны две таблицы как на бланке — фильтруйте по `teamId` и нумеруйте строки
внутри команды сами.

**Передач бывает 0, 1 или 2.** `assists` и `assistNumbers` — параллельные массивы одной длины.

`time` — время **внутри периода**. Абсолютного времени от начала матча в данных нет, его нет
и в бумажном протоколе. Показывать логично как «1 период, 13:36».

---

## GET /tournaments/{id}/players

Вся заявка турнира со статистикой. **Незаигравшие приходят с нулями, а не пропадают** —
готовый список для страницы «Состав».

Полевой игрок:

```json
{
  "player": { "id": "a119ead3-…", "fullName": "Рогов Савелий", "photo": null, "position": null, "birthDate": null },
  "team": { "id": "3f6c3db1-…", "name": "Импульс", "city": null, "logo": "https://…" },
  "number": 13,
  "games": 3, "goals": 6, "assists": 2, "points": 8,
  "isGoalie": false,
  "goalsAgainst": null, "saves": null, "minutesPlayed": null
}
```

Вратарь — те же поля, но заполнены вратарские:

```json
{ "number": 35, "games": 3, "isGoalie": true, "goalsAgainst": 24, "saves": 60, "minutesPlayed": 90 }
```

| Поле | Прим. |
|---|---|
| `number` | Игровой номер **в этом турнире**. У одного игрока в разных турнирах может отличаться |
| `games` | В скольких матчах турнира игрок значится в протоколе |
| `points` | `goals + assists` |
| `isGoalie` | Стоял в воротах хотя бы в одном матче турнира |
| `goalsAgainst` / `saves` / `minutesPlayed` | Только у вратарей, иначе `null`. См. [statistics.md](statistics.md) |

Рисуйте две таблицы — полевых и вратарей, фильтруя по `isGoalie`: осмысленные колонки у них
разные.

---

## GET /tournaments/{id}/best-players

Бомбардиры по `goals + assists`. Формат элемента тот же, что в `/players`.

| Параметр | По умолчанию | Диапазон |
|---|---|---|
| `limit` | `10` | 1…100 |

Уже отсортировано: `очки → голы → ФИО`. **Незаигравшие в список не попадают** (в отличие
от `/players`). Команда всегда заполнена.

```bash
curl -s "https://api.timeofthestars-kids.ru/tournaments/{id}/best-players?limit=5"
```

---

## GET /players/{id}/stats

Карточка игрока: карьера по всем турнирам плюс разбивки.

| Параметр | Прим. |
|---|---|
| `tournament_id` | Необязательный фильтр |
| `team_id` | Необязательный фильтр |

Фильтры применяются **ко всем трём блокам сразу**, а не только к `career`.

```json
{
  "player": { "id": "82461ace-…", "fullName": "Едигарев Роман", "photo": null, "position": "вратарь", "birthDate": null },
  "career": {
    "games": 3, "goals": 0, "assists": 0, "points": 0,
    "goalsAgainst": 24, "saves": 60, "minutesPlayed": 90
  },
  "byTournament": [
    { "id": "95f35be3-…", "name": "Летний Кубок", "totals": { "games": 3, "goals": 0, "assists": 0, "points": 0, "goalsAgainst": 24, "saves": 60, "minutesPlayed": 90 } }
  ],
  "byTeam": [
    { "id": "ffbcfc25-…", "name": "Искра", "totals": { "games": 3, "goals": 0, "assists": 0, "points": 0, "goalsAgainst": 24, "saves": 60, "minutesPlayed": 90 } }
  ]
}
```

У полевых игроков вратарские поля — `null`. Игрок, менявший команду между турнирами,
корректно раскладывается по `byTeam`.

Несуществующий игрок — `404 {"detail": "Игрок не найден"}`.

---

## GET /teams

Справочник команд с общей статистикой за всю историю.

| Параметр | По умолчанию | Диапазон |
|---|---|---|
| `skip` | `0` | ≥ 0 |
| `limit` | `200` | 1…500 |

```json
{
  "id": "ffbcfc25-…",
  "name": "Локомотив",
  "city": "Ярославль",
  "logo": "https://…/static/teams/….png",
  "description": null,
  "stats": {
    "tournaments": 1, "games": 3,
    "wins": 1, "draws": 0, "losses": 2,
    "goalsFor": 13, "goalsAgainst": 13, "goalDiff": 0, "points": 2
  }
}
```

| Поле | Смысл |
|---|---|
| `tournaments` | Турниров, где у команды есть хотя бы один матч с заполненным счётом |
| `games` | Матчей с заполненным счётом |
| `wins` / `draws` / `losses` | По результату матча |
| `goalsFor` / `goalsAgainst` / `goalDiff` | Шайбы за всю историю |
| `points` | 2 за победу, 1 за ничью |

> ⚠️ Показатели могут включать **поправку на историю вне системы**, заданную администратором.
> Подробно — [statistics.md](statistics.md).

## GET /teams/{id}

Один объект той же формы. Несуществующая команда — `404 {"detail": "Команда не найдена"}`.

---

## POST /appointments

Запись на тренировку с сайта.

```bash
curl -s -X POST https://api.timeofthestars-kids.ru/appointments \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+79001234567","parent_name":"Орлов Алексей","child_name":"Орлов Иван","child_age":7}'
```

| Поле | Тип | Прим. |
|---|---|---|
| `phone` | string ≤ 64 | обязательно |
| `parent_name` | string ≤ 255 | обязательно |
| `child_name` | string ≤ 255 | обязательно |
| `child_age` | integer 0…18 | обязательно |

Ответ `201`:

```json
{ "id": "…", "status": "created" }
```

`status` равен `created_notify_failed`, если запись сохранена, но уведомление в VK не ушло.
Для сайта разницы нет — заявка принята в обоих случаях.

Тело этих форм — **snake_case**: это данные, уходящие в кабинет, а не читаемые фронтом.

---

## POST /service-requests

То же плюс услуга.

| Поле | Тип |
|---|---|
| `phone` | string ≤ 64, обязательно |
| `parent_name` | string ≤ 255, обязательно |
| `child_name` | string ≤ 255, обязательно |
| `child_age` | integer 0…18, обязательно |
| `service` | string ≤ 512, обязательно |

---

## POST /questions

| Поле | Тип |
|---|---|
| `full_name` | string ≤ 255, обязательно |
| `contact` | string ≤ 255, обязательно — телефон, почта или ссылка |
| `question` | string ≤ 4000, обязательно |

---

## POST /tournament-applications/player

Заявка ребёнка на турнир.

| Поле | Тип |
|---|---|
| `parent_name` | string ≤ 255, обязательно |
| `child_name` | string ≤ 255, обязательно |
| `child_age` | integer 0…18, обязательно |
| `phone` | string ≤ 64, обязательно |

## POST /tournament-applications/team

Заявка команды на турнир.

| Поле | Тип |
|---|---|
| `team_name` | string ≤ 255, обязательно |
| `city` | string ≤ 255, обязательно |
| `age_category` | string ≤ 32, обязательно |
| `coach_name` | string ≤ 255, обязательно |
| `phone` | string ≤ 64, обязательно |
| `comment` | string, необязательно |

---

## GET /reviews

Отзывы, вытянутые из обсуждения VK или добавленные вручную. Только видимые, в порядке
`position`.

| Параметр | По умолчанию |
|---|---|
| `limit` | без ограничения, если не задан |

```json
[ { "text": "Отличная школа…", "author": "Мария", "pic": "https://…" } ]
```

## GET /news

Превью постов со стены VK. Только видимые.

```json
[ { "image": "https://…", "excerpt": "Итоги турнира…", "url": "https://vk.com/wall-…" } ]
```

---

## Сервисные ручки

### GET /health

```json
{ "status": "ok" }
```

Используется smoke-тестом деплоя: если ручка не ответила `200`, автодеплой откатывается
на предыдущий образ.

### GET /

Самоописание сервиса — версия и список основных маршрутов. Удобно, чтобы быстро убедиться,
что задеплоена нужная версия.

```json
{
  "service": "Time of the Stars Kids API",
  "version": "0.1.0",
  "docs": "/docs",
  "health": "/health",
  "admin_ui": "/admin/",
  "tournaments": "GET /tournaments"
}
```
