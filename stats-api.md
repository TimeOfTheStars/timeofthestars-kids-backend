# Статистика турниров — API для фронта

Дополнение к `tournaments-api.md`. Описывает то, что появилось вместе со статистикой турниров:
таблицу, матчи, протокол матча, игроков и карточку игрока.

База: `https://api.timeofthestars-kids.ru`

**Ломающих изменений нет.** Всё, что было, отвечает как раньше; `GET /tournaments` только
получил новые поля. Все примеры ниже — настоящие ответы сервиса на данных бумажного протокола
турнира «Летний кубок», матч №1 ХК «ИСКРА» — ХК «ИМПУЛЬС» (табло 1:8, броски 8:26).

---

## Оглавление

- [Что нужно знать до начала](#что-нужно-знать-до-начала)
- [Изменения в `GET /tournaments`](#изменения-в-get-tournaments)
- [`GET /tournaments/{id}/standings`](#get-tournamentsidstandings) — таблица
- [`GET /tournaments/{id}/games`](#get-tournamentsidgames) — матчи
- [`GET /games/{id}`](#get-gamesid) — матч с протоколом
- [`GET /tournaments/{id}/players`](#get-tournamentsidplayers) — игроки турнира
- [`GET /tournaments/{id}/best-players`](#get-tournamentsidbest-players) — бомбардиры
- [`GET /players/{id}/stats`](#get-playersidstats) — карточка игрока
- [`GET /teams` и `GET /teams/{id}`](#get-teams-и-get-teamsid) — команды и их общая статистика
- [Подводные камни](#подводные-камни)
- [Админские ручки](#админские-ручки)

---

## Что нужно знать до начала

**Ничего не хранится в готовом виде.** Таблица, очки, бомбардиры и статистика игроков считаются
на лету по сырым данным (матчи, составы, голы). Поэтому цифры всегда согласованы между собой,
но и кешировать их на фронте надолго не стоит — все ответы приходят с
`Cache-Control: public, max-age=300`.

**Публичные ответы — camelCase**, как и в `tournaments-api.md` (`goalsFor`, `isFinished`,
`matchNo`). Админские — snake_case, это другой контур.

**Стадий и плей-офф нет.** Турнир — плоский список матчей, в таблицу идут все матчи
с заполненным счётом. Никакой сетки, «1/4», «финала» в данных не существует.

**Начинайте с `hasStats`.** У большинства турниров статистики нет и не будет (старые записи).
Поле `hasStats` в `GET /tournaments` говорит, есть ли хотя бы один сыгранный матч, — по нему
и решайте, показывать ли блок статистики, не делая лишних запросов.

**Скрытый турнир — 404.** Если `is_visible = false`, все ручки статистики по нему отдают
`404 {"detail": "Турнир не найден"}`, а не пустой массив.

**Пути к файлам абсолютные.** `logo`, `photo`, `scan` приходят полными URL.

---

## Изменения в `GET /tournaments`

Добавлены четыре поля. У турниров, заведённых до появления статистики, первые три — `null`,
`hasStats` — `false`. В `teams[]` у каждой команды появился `city` (`null`, если не заполнен).

| Поле | Тип | Смысл |
|---|---|---|
| `gameFormat` | `string \| null` | Формат игры из шапки протокола, например `"4-4"` |
| `periodMinutes` | `number \| null` | Длительность периода в минутах |
| `periodsCount` | `number \| null` | Количество периодов |
| `hasStats` | `boolean` | Есть ли хотя бы один сыгранный матч |

```jsonc
// GET /tournaments  → элемент массива
{
  "id": "e1b78014-fd8e-4fd7-be55-f3f5367179b4",
  "title": "Летний кубок",
  "ageCategory": "2018-19",
  "birthYear": "2018-19",
  "startDate": "2026-08-23",
  "endDate": "2026-08-23",
  "startTime": null,
  "endTime": null,
  "arena": { "name": "ГУОР по хоккею", "url": null, "address": null, "city": "Ярославль" },
  "season": "2026/2027",
  "description": null,
  "url": null,
  "recordingsUrl": null,

  // ↓ новое
  "gameFormat": "4-4",
  "periodMinutes": 15,
  "periodsCount": 3,
  "hasStats": true,

  "teams": [
    { "name": "ХК «ИСКРА»",   "city": "Ярославль", "logo": null, "photo": null },
    { "name": "ХК «ИМПУЛЬС»", "city": "Ярославль", "logo": null, "photo": null }
  ]
}
```

> ⚠️ В `teams` здесь по-прежнему нет `id` — это исторический формат, он не менялся.
> Идентификаторы команд приходят в ручках статистики ниже.

---

## GET /tournaments/{id}/standings

Таблица турнира. **Уже отсортирована сервером** — место равно `place`, оно же индекс + 1.
Не пересортировывайте: порядок задаёт цепочка `очки → разница шайб → забитые шайбы → название`,
и воспроизводить её на фронте незачем.

Очки: **победа 2, ничья 1, поражение 0**. Дополнительного времени и буллитов в схеме нет.

```bash
curl -s https://api.timeofthestars-kids.ru/tournaments/{id}/standings
```

```json
[
  {
    "place": 1,
    "team": { "id": "3f6c3db1-…", "name": "ХК «ИМПУЛЬС»", "city": "Ярославль", "logo": null },
    "games": 1,
    "wins": 1,
    "draws": 0,
    "losses": 0,
    "goalsFor": 8,
    "goalsAgainst": 1,
    "goalDiff": 7,
    "points": 2
  },
  {
    "place": 2,
    "team": { "id": "ffbcfc25-…", "name": "ХК «ИСКРА»", "city": "Ярославль", "logo": null },
    "games": 1, "wins": 0, "draws": 0, "losses": 1,
    "goalsFor": 1, "goalsAgainst": 8, "goalDiff": -7, "points": 0
  }
]
```

Команда, заявленная в турнир, но ещё не игравшая, **присутствует в таблице с нулями** —
её не нужно доставать отдельно. При равных очках она окажется выше проигравшей команды
с отрицательной разницей: это следствие цепочки tie-break, а не ошибка.

---

## GET /tournaments/{id}/games

Календарь и результаты в порядке «МАТЧ №». Незаполненные поля табло — `null`,
это нормальное состояние ещё не сыгранного матча.

```bash
curl -s https://api.timeofthestars-kids.ru/tournaments/{id}/games
```

```json
[
  {
    "id": "0ac3a154-14a1-46c5-925f-77f9fcfc9aa2",
    "matchNo": 1,
    "date": "2026-08-23",
    "time": null,
    "teamA": { "id": "ffbcfc25-…", "name": "ХК «ИСКРА»",   "city": "Ярославль", "logo": null },
    "teamB": { "id": "3f6c3db1-…", "name": "ХК «ИМПУЛЬС»", "city": "Ярославль", "logo": null },
    "scoreA": 1,
    "scoreB": 8,
    "shotsA": 8,
    "shotsB": 26,
    "videoUrl": null,
    "scan": null,
    "isFinished": true
  }
]
```

| Поле | Прим. |
|---|---|
| `matchNo` | Номер матча в турнире, он же порядок сортировки |
| `scoreA` / `scoreB` | «Голы» из табло |
| `shotsA` / `shotsB` | «Броски» из табло. Из них выводится вратарская статистика |
| `scan` | Скан бумажного протокола (картинка или PDF), `null` если не приложен |
| `isFinished` | `true`, когда заполнены **оба** счёта. Ставится сервером, вручную не задаётся |

`time` приходит как `"HH:MM"` или `null`.

---

## GET /games/{id}

Матч с протоколом: составы обеих команд и хронология голов. Это данные для страницы матча.

```bash
curl -s https://api.timeofthestars-kids.ru/games/{id}
```

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
      "team": { "id": "ffbcfc25-…", "name": "ХК «ИСКРА»", "city": "Ярославль", "logo": null },
      "number": 35,
      "games": 1,
      "goals": 0,
      "assists": 0,
      "points": 0,
      "isGoalie": true,
      "goalsAgainst": 8,     // пропущено в ЭТОМ матче
      "saves": 18,           // отражено = броски соперника − его голы
      "minutesPlayed": 45
    }
    // … остальные игроки
  ],
  "rosterB": [ /* то же для второй команды */ ],

  "goals": [
    {
      "period": 1,
      "time": "00:02",
      "teamId": "ffbcfc25-…",
      "scorer": { "id": "0469426f-…", "fullName": "Ефименко Даниил", "photo": null, "position": null, "birthDate": null },
      "scorerNumber": 97,
      "assists": [],
      "assistNumbers": []
    },
    {
      "period": 1,
      "time": "13:36",
      "teamId": "3f6c3db1-…",
      "scorer": { "id": "37bcbe3a-…", "fullName": "Самыловский Егор", "photo": null, "position": null, "birthDate": null },
      "scorerNumber": 12,
      "assists": [
        { "id": "82b753ab-…", "fullName": "Пустовойтов Лев", "photo": null, "position": null, "birthDate": null }
      ],
      "assistNumbers": [2]
    }
  ]
}
```

**Состав — это те, кто реально играл**, а не вся заявка на турнир. Отсортирован так же, как
в бумажном бланке: сначала вратари, потом остальные по возрастанию номера. `games` в строке
состава всегда `1` — это статистика конкретного матча.

**`goals` — единый массив на обе команды**, уже в правильном порядке. Команда определяется
по `teamId`. Если нужны две таблицы как на бланке — фильтруйте по `teamId` и нумеруйте строки
внутри каждой команды сами.

**Передач может быть 0, 1 или 2.** `assists` и `assistNumbers` — параллельные массивы
одинаковой длины, порядок соответствует бланку.

`time` — это время **внутри периода** в формате `MM:SS`. Абсолютного времени от начала матча
в данных нет: в бумажном протоколе его тоже нет. Показывать логично как `1 период, 13:36`.

---

## GET /tournaments/{id}/players

Вся заявка турнира со статистикой. **Незаигравшие приходят с нулями, а не пропадают** —
это готовый список для страницы «Состав».

```bash
curl -s https://api.timeofthestars-kids.ru/tournaments/{id}/players
```

Полевой игрок:

```json
{
  "player": { "id": "a119ead3-…", "fullName": "Рогов Савелий", "photo": null, "position": null, "birthDate": null },
  "team": { "id": "3f6c3db1-…", "name": "ХК «ИМПУЛЬС»", "city": "Ярославль", "logo": null },
  "number": 13,
  "games": 1,
  "goals": 4,
  "assists": 0,
  "points": 4,
  "isGoalie": false,
  "goalsAgainst": null,
  "saves": null,
  "minutesPlayed": null
}
```

Вратарь:

```json
{
  "player": { "id": "cd7e9a5f-…", "fullName": "Малахов Дмитрий", "photo": null, "position": "вратарь", "birthDate": null },
  "team": { "id": "3f6c3db1-…", "name": "ХК «ИМПУЛЬС»", "city": "Ярославль", "logo": null },
  "number": 1,
  "games": 1,
  "goals": 0,
  "assists": 0,
  "points": 0,
  "isGoalie": true,
  "goalsAgainst": 1,
  "saves": 7,
  "minutesPlayed": 45
}
```

| Поле | Смысл |
|---|---|
| `number` | Игровой номер **в этом турнире**. У одного игрока в разных турнирах он может отличаться |
| `games` | В скольких матчах турнира игрок значится в протоколе |
| `points` | `goals + assists` |
| `isGoalie` | Стоял ли в воротах хотя бы в одном матче турнира |
| `goalsAgainst` / `saves` / `minutesPlayed` | Только для вратарей, иначе `null`. См. оговорки ниже |

Рисуйте две таблицы — полевых и вратарей — фильтруя по `isGoalie`: набор осмысленных колонок
у них разный.

---

## GET /tournaments/{id}/best-players

Бомбардиры по `goals + assists`. Формат элемента тот же, что в `/players`.

```bash
curl -s "https://api.timeofthestars-kids.ru/tournaments/{id}/best-players?limit=3"
```

| Параметр | По умолчанию | Диапазон |
|---|---|---|
| `limit` | `10` | 1…100 |

Уже отсортировано: `очки → голы → ФИО`. **Незаигравшие в список не попадают** (в отличие
от `/players`). Команда всегда заполнена.

```json
[
  { "player": { "fullName": "Рогов Савелий", "…": "…" },     "number": 13, "games": 1, "goals": 4, "assists": 0, "points": 4, "team": { "name": "ХК «ИМПУЛЬС»", "…": "…" } },
  { "player": { "fullName": "Самыловский Егор", "…": "…" }, "number": 12, "games": 1, "goals": 1, "assists": 2, "points": 3, "team": { "name": "ХК «ИМПУЛЬС»", "…": "…" } },
  { "player": { "fullName": "Аксёнтов Андрей", "…": "…" },  "number": 9,  "games": 1, "goals": 1, "assists": 1, "points": 2, "team": { "name": "ХК «ИМПУЛЬС»", "…": "…" } }
]
```

---

## GET /players/{id}/stats

Карточка игрока: карьера по всем турнирам плюс разбивки.

```bash
curl -s https://api.timeofthestars-kids.ru/players/{id}/stats
curl -s "https://api.timeofthestars-kids.ru/players/{id}/stats?tournament_id={tid}"
curl -s "https://api.timeofthestars-kids.ru/players/{id}/stats?team_id={teamId}"
```

Оба фильтра необязательны и применяются **ко всем трём блокам сразу**, а не только к `career`.

```json
{
  "player": { "id": "82461ace-…", "fullName": "Едигарев Роман", "photo": null, "position": "вратарь", "birthDate": null },
  "career": {
    "games": 1, "goals": 0, "assists": 0, "points": 0,
    "goalsAgainst": 8, "saves": 18, "minutesPlayed": 45
  },
  "byTournament": [
    {
      "id": "29784fe1-…",
      "name": "Летний кубок",
      "totals": { "games": 1, "goals": 0, "assists": 0, "points": 0, "goalsAgainst": 8, "saves": 18, "minutesPlayed": 45 }
    }
  ],
  "byTeam": [
    {
      "id": "5422d7eb-…",
      "name": "ХК «ИСКРА»",
      "totals": { "games": 1, "goals": 0, "assists": 0, "points": 0, "goalsAgainst": 8, "saves": 18, "minutesPlayed": 45 }
    }
  ]
}
```

У полевых игроков вратарские поля — `null`. Игрок, менявший команду между турнирами,
корректно раскладывается по `byTeam`.

Несуществующий игрок — `404 {"detail": "Игрок не найден"}`.

---

## GET /teams и GET /teams/{id}

Справочник команд с общей статистикой за всю историю. Раньше публичного доступа
к командам не было вовсе.

```bash
curl -s https://api.timeofthestars-kids.ru/teams
curl -s "https://api.timeofthestars-kids.ru/teams?limit=50&skip=0"
curl -s https://api.timeofthestars-kids.ru/teams/{id}
```

```json
{
  "id": "ffbcfc25-4b5d-461a-b15c-1c05be15e218",
  "name": "Локомотив",
  "city": "Ярославль",
  "logo": "https://api.timeofthestars-kids.ru/static/teams/….png",
  "description": null,
  "stats": {
    "tournaments": 1,
    "games": 3,
    "wins": 1,
    "draws": 0,
    "losses": 2,
    "goalsFor": 13,
    "goalsAgainst": 13,
    "goalDiff": 0,
    "points": 2
  }
}
```

`GET /teams` отдаёт массив таких объектов, `GET /teams/{id}` — один; несуществующая
команда даёт `404 {"detail": "Команда не найдена"}`.

| Поле | Смысл |
|---|---|
| `tournaments` | Турниров, где у команды есть хотя бы один матч с заполненным счётом |
| `games` | Матчей с заполненным счётом |
| `wins` / `draws` / `losses` | По результату матча |
| `goalsFor` / `goalsAgainst` / `goalDiff` | Шайбы за всю историю |
| `points` | 2 за победу, 1 за ничью |

Параметры `skip` (от 0) и `limit` (1…500, по умолчанию 200) — только у списка.

> ⚠️ Часть показателей может быть **вписана вручную** — см. подводный камень 7.

---

## Подводные камни

Собрано отдельно — это те места, где данные ведут себя не так, как можно было бы ожидать.

### 1. Вратарские показатели — производные от табло, а не измеренные

В бумажном протоколе броски и голы записываются **по команде целиком**, отдельной строки
на вратаря нет. Отсюда:

- `goalsAgainst` = голы соперника в матче;
- `saves` = броски соперника − голы соперника;
- `saves` равно `null`, если броски в табло **не заполнены** — процент отражённых в этом
  случае посчитать нельзя, показывайте прочерк;
- если в матче у команды было отмечено **двое вратарей**, распределить командные цифры между
  ними невозможно, и такой матч **не входит** в их `goalsAgainst`/`saves`. В `games` он при
  этом учтён — то есть у вратаря может быть 3 игры и цифры только за 2 из них.

**`minutesPlayed` — не фактическое время на льду.** Это `periodMinutes × periodsCount`,
то есть длительность матча по регламенту, начисленная в предположении, что вратарь отыграл
всё. Подписывать как «время в воротах» корректно, как «сыграно минут» — нет. Если регламент
у турнира не заполнен, поле придёт `null`.

Процент отражённых броском сервер не считает — при необходимости считайте на фронте
как `saves / (saves + goalsAgainst)`, предварительно проверив, что `saves !== null`.

### 2. Сумма голов игроков равна счёту матча

Буллитов, голов в пустые ворота и прочих особых типов в схеме нет — событие бывает только
одно, «гол». Поэтому `количество голов команды в timeline === scoreA/scoreB`, и на этом можно
строить проверки. (В соседнем проекте это не так — там голы с буллитов расходились со счётом.
Здесь такого нет.)

### 3. Периода в бумаге нет — он вводится вручную

Поле `period` заполняет секретарь при вводе, на бланке его не печатают. Практически это
значит, что у старых матчей период может быть проставлен формально (всё в первом). Не строьте
логику, критично зависящую от разбивки по периодам.

### 4. Числа могут быть не согласованы между блоками, если протокол заполнен наполовину

Табло (`scoreA`/`scoreB`) и таймлайн голов вводятся в одной форме, но независимо. Админка
подсвечивает расхождение, однако сохранить такой протокол всё равно можно. Если для вас важно, что
`goals.length` совпадает с суммой счёта, — проверяйте это на фронте и деградируйте мягко.

### 5. `games` в разных ручках означает разное

- в `/tournaments/{id}/players` и `/players/{id}/stats` — число матчей;
- в составе внутри `/games/{id}` — всегда `1`, это статистика одного матча.

### 6. Статистика команды может быть вписана руками

В `GET /teams` и `GET /teams/{id}` любой из показателей может быть не рассчитан, а вписан
администратором — так заводят историю турниров, матчи которых в систему ещё не внесены.

Важное следствие: **вписанное значение не пересчитывается**. Если у команды стоит
«games = 23», то после нового заведённого матча там по-прежнему будет 23, пока цифру не
поправят руками. Публичный API **не показывает**, какие показатели ручные, поэтому:

- сумма по матчам турнира может не совпадать с общей статистикой команды — это не ошибка;
- `games` не обязан равняться `wins + draws + losses`, если переопределена только часть полей;
- `points` всегда согласованы с `wins` и `draws` того же ответа: очки не переопределяются,
  а выводятся из действующих побед и ничьих.

Если нужна заведомо честная арифметика по данным системы — считайте её из
`/tournaments/{id}/standings` и `/tournaments/{id}/games`, они не переопределяются.

### 7. Порядок отдаёт сервер

`standings` и `best-players` приходят отсортированными, `games` — в порядке `matchNo`,
`goals` — в хронологическом порядке ввода, состав в `/games/{id}` — вратари первыми, дальше
по номеру. Пересортировка на фронте только всё испортит.

---

## Админские ручки

Нужны кабинету, публичному фронту — нет. Все требуют `Authorization: Bearer <token>`,
формат тела и ответов — **snake_case**.

### Справочник игроков

```
GET    /api/admin/players?limit=500&search=Гвоздев
POST   /api/admin/players            { full_name, birth_date?, position?, photo? }
PATCH  /api/admin/players/{id}
DELETE /api/admin/players/{id}
POST   /api/admin/uploads/player-photo     (multipart, поле file) → { url }
```

`position` — одно из `вратарь` / `защитник` / `нападающий` либо `null`.

### Заявка на турнир

```
GET    /api/admin/tournaments/{id}/roster
POST   /api/admin/tournaments/{id}/roster  { team_id, players: [{ player_id, number? }] }
PATCH  /api/admin/tournaments/{id}/roster/{entryId}   { number }
DELETE /api/admin/tournaments/{id}/roster/{entryId}
```

```json
{
  "id": "8a32c530-…",
  "team_id": "5422d7eb-…",
  "team_name": "ХК «ИСКРА»",
  "player_id": "3552e611-…",
  "full_name": "Трофимов Мирон",
  "birth_date": null,
  "position": null,
  "photo": null,
  "number": 2
}
```

Номер уникален внутри команды турнира: повтор — `409`. Пустой номер разрешён любому числу
игроков.

### Матчи

```
GET    /api/admin/tournaments/{id}/games
POST   /api/admin/tournaments/{id}/games
GET    /api/admin/games/{id}
PATCH  /api/admin/games/{id}
DELETE /api/admin/games/{id}
POST   /api/admin/uploads/game-scan       (multipart, поле file; картинка или PDF, до 10 МБ)
```

Обе команды обязаны быть заявлены в турнир, иначе `400`. Сменить команды у матча
с заполненным протоколом нельзя — `409`.

### Протокол — единственный путь записи статистики

```
GET /api/admin/games/{id}/protocol
PUT /api/admin/games/{id}/protocol
```

```jsonc
// PUT — тело
{
  "score_a": 1, "score_b": 8,
  "shots_a": 8, "shots_b": 26,

  // кто играл; голы и передачи здесь НЕ принимаются
  "stat_lines": [
    { "player_id": "…", "team_id": "…", "is_goalie": true },
    { "player_id": "…", "team_id": "…", "is_goalie": false }
  ],

  // таблица «ВЗЯТИЕ ВОРОТ»
  "events": [
    { "team_id": "…", "period": 1, "time": "13:36",
      "player_id": "…", "assist1_player_id": "…", "assist2_player_id": null }
  ]
}
```

Голы и передачи **выводятся из `events`** и перезаписываются при каждом сохранении. Прислать
`goals`/`assists` в `stat_lines` нельзя — вернётся `422` (защита от устаревшего клиента,
который иначе молча обнулил бы цифры).

`events` имеет три состояния:

| Значение | Поведение |
|---|---|
| поле не передано | таймлайн не трогаем, производные пересчитываем из того, что в базе |
| `[]` | таймлайн очищаем, голы и передачи обнуляем |
| массив | полная замена таймлайна |

`time` принимается как `MM:SS`, но терпит и `1336`, и `15м`, и `2м30с`. Валидация: время
не больше длительности периода, период не больше `periodsCount + 1` (последний — овертайм),
автор и оба ассистента обязаны иметь строку участия **за ту же команду**, ассистент не равен
автору и не дублируется. Любое нарушение — `422` с текстом на русском, ничего не записывается.

Ответ — расширенный протокол:

```jsonc
{
  "game": { /* GameListItem, snake_case */ },
  "period_minutes": 15,
  "periods_count": 3,
  "stat_lines": [
    { "player_id": "…", "team_id": "…", "full_name": "Степанов Артём", "number": 11,
      "position": null, "is_goalie": false, "goals": 0, "assists": 0, "points": 0,
      "goals_against": null, "saves": null }
  ],
  "events": [
    { "id": "…", "team_id": "…", "period": 1, "time": "13:36", "time_seconds": 816,
      "sort_order": 2, "player_id": "…", "player_name": "Самыловский Егор", "player_number": 12,
      "assist1_player_id": "…", "assist1_name": "Пустовойтов Лев", "assist1_number": 2,
      "assist2_player_id": null, "assist2_name": null, "assist2_number": null }
  ],
  "goals_in_timeline_a": 1,
  "goals_in_timeline_b": 8,
  "goalie_ambiguous_team_ids": []
}
```

- `goals_in_timeline_a/b` — для сверки со счётом, кабинет подсвечивает расхождение;
- `goalie_ambiguous_team_ids` — команды, где вратарей ноль или больше одного, то есть
  вратарские за этот матч не начислены;
- `sort_order` — порядок **в пределах матча**, а не номер строки бланка. У первого гола
  второй команды он вполне может быть `2`, если до него забила первая. Нумеровать строки
  двух таблиц как на бумаге нужно самостоятельно, внутри команды.
