# API кабинета

Префикс `/api/admin`. Все ручки, кроме логина, требуют `Authorization: Bearer <token>`.
Поля — **snake_case**.

## Оглавление

- [Авторизация и роли](#авторизация-и-роли)
- [Общие соглашения](#общие-соглашения)
- [Профиль и пользователи](#профиль-и-пользователи)
- [Заявки с сайта](#заявки-с-сайта)
- [Отзывы](#отзывы) · [Новости](#новости)
- [Арены](#арены) · [Команды](#команды) · [Игроки](#игроки)
- [Турниры](#турниры) · [Заявка на турнир](#заявка-на-турнир-состав)
- [Матчи](#матчи) · [Протокол матча](#протокол-матча)
- [Загрузка файлов](#загрузка-файлов)

---

## Авторизация и роли

### POST /api/admin/auth/login

Единственная ручка без токена.

```bash
curl -s -X POST https://api.timeofthestars-kids.ru/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"…"}'
```

```json
{ "access_token": "eyJ…", "token_type": "bearer" }
```

Неверная пара — `401 {"detail":"Неверный логин или пароль"}`, отключённый пользователь —
`403 {"detail":"Пользователь отключён"}`.

Время жизни токена задаётся переменной `JWT_EXPIRE_MINUTES`.

### Роли

| Роль | Может |
|---|---|
| `admin` | всё, включая управление пользователями |
| `viewer` | всё, кроме `/admins` — там `403` |

Последнего активного администратора нельзя ни отключить, ни понизить в роли.

---

## Общие соглашения

**PATCH принимает только изменённые поля.** Тело собирается через `exclude_unset`, поэтому
пустой объект даёт `400 {"detail":"Нет полей для обновления"}`. Явный `null` — это
осмысленное «очистить поле», а не «не менять».

**Пустая строка приводится к `null`** для необязательных текстовых полей — можно смело
отправлять то, что ввели в форму.

**Списки** принимают `skip` (≥ 0) и `limit`, если не указано иное.

**`DELETE` на коллекцию** (`/teams`, `/reviews`, `/news`, `/tournaments`, `/appointments`,
`/questions`, `/service-requests`, `/tournament-applications/*`) удаляет всё и возвращает
`{"deleted": <число>}`. Удаление одного объекта отвечает `204` без тела.

---

## Профиль и пользователи

| Метод | Путь | Прим. |
|---|---|---|
| `GET` | `/me` | Текущий пользователь: `id`, `username`, `role`, `vk_user_id` |
| `PATCH` | `/me/vk` | `{ "vk_user_id": 254901637 \| null }` — куда присылать уведомления |
| `GET` | `/admins` | Только роль `admin`. `skip`, `limit` |
| `POST` | `/admins` | `{ username, password, vk_user_id?, role? }`, `role` по умолчанию `viewer` |
| `PATCH` | `/admins/{user_id}` | `{ username?, password?, vk_user_id?, role?, is_active? }` |

---

## Заявки с сайта

Четыре однотипных раздела: только чтение и удаление — создаются они публичными ручками.

| Раздел | Путь | Поля записи |
|---|---|---|
| Запись на тренировку | `/appointments` | `phone`, `parent_name`, `child_name`, `child_age` |
| Заявка на услугу | `/service-requests` | те же + `service` |
| Вопрос | `/questions` | `full_name`, `contact`, `question` |
| Заявка игрока на турнир | `/tournament-applications/players` | `parent_name`, `child_name`, `child_age`, `phone` |
| Заявка команды на турнир | `/tournament-applications/teams` | `team_name`, `city`, `age_category`, `coach_name`, `phone`, `comment` |

Для каждого: `GET <путь>` (список), `DELETE <путь>/{id}` (одну), `DELETE <путь>` (все).
У заявок на турнир идентификатор в пути называется `{app_id}`.

---

## Отзывы

| Метод | Путь | Прим. |
|---|---|---|
| `GET` | `/reviews` | `skip`, `limit` |
| `POST` | `/reviews` | `{ text, author_name, author_photo_url?, position?, is_visible? }` |
| `PATCH` | `/reviews/{review_id}` | те же поля, все необязательные |
| `DELETE` | `/reviews/{review_id}` · `/reviews` | одну · все |
| `POST` | `/reviews/sync` | Подтянуть новые комментарии из обсуждения VK |

`sync` идемпотентен: существующие записи не трогает, дедуплицирует по `vk_comment_id`.
Возвращает сводку `{ fetched, created, skipped_existing, skipped_empty }`.

---

## Новости

| Метод | Путь | Прим. |
|---|---|---|
| `GET` | `/news` | `skip`, `limit` |
| `POST` | `/news` | `{ url, position?, is_visible? }` — остальное вытягивается из VK по ссылке |
| `PATCH` | `/news/{news_id}` | |
| `DELETE` | `/news/{news_id}` · `/news` | |
| `POST` | `/news/sync` | Последние посты со стены группы |
| `POST` | `/news/{news_id}/refresh` | Перечитать один пост из VK |

Дедупликация по паре `vk_owner_id` + `vk_post_id`. Посты, начинающиеся с
`ПРЯМЫЕ ТРАНСЛЯЦИИ`, синхронизация пропускает. Сводка:
`{ fetched, created, skipped_existing, skipped_empty, skipped_filtered }`.

Ошибки VK превращаются в `502` с понятным текстом — чтении стены нужен отдельный
`VK_READ_TOKEN`, групповой токен для этого не годится.

---

## Арены

Справочник площадок, на которые ссылаются турниры.

| Метод | Путь | Тело |
|---|---|---|
| `GET` | `/arenas` | `skip`, `limit` |
| `POST` | `/arenas` | `{ name, url?, address?, city? }` |
| `PATCH` | `/arenas/{arena_id}` | те же, все необязательные |
| `DELETE` | `/arenas/{arena_id}` | `204` |

`url` — ссылка на Яндекс.Карты. Удалить арену, на которую ссылается турнир, нельзя:
FK стоит с `RESTRICT`.

---

## Команды

| Метод | Путь |
|---|---|
| `GET` | `/teams` — `skip`, `limit` |
| `POST` | `/teams` |
| `PATCH` | `/teams/{team_id}` |
| `DELETE` | `/teams/{team_id}` · `/teams` |

### Тело запроса

| Поле | Тип | Прим. |
|---|---|---|
| `name` | string ≤ 255 | обязательно при создании |
| `city` | string ≤ 255 \| null | |
| `logo` | string ≤ 1024 \| null | URL из `/uploads/team-logo` |
| `description` | string ≤ 2000 \| null | Используется как подпись в выборе команд турнира |
| `total_tournaments` | int \| null | ↓ желаемые **итоги** общей статистики |
| `total_games` | int \| null | |
| `total_wins` | int \| null | |
| `total_draws` | int \| null | |
| `total_losses` | int \| null | |
| `total_goals_for` | int \| null | |
| `total_goals_against` | int \| null | |

**`total_*` — это итог, а не дельта.** Сервер вычтет из него свежий расчёт по матчам и
сохранит разницу как поправку, поэтому статистика продолжит считаться. `null` убирает
поправку. Очки не задаются — выводятся из итоговых побед и ничьих. Подробно:
[statistics.md](statistics.md).

### Ответ

```jsonc
{
  "id": "ffbcfc25-…",
  "name": "Локомотив",
  "city": "Ярославль",
  "logo": "https://…",
  "description": null,

  "stats":    { "tournaments": 7, "games": 23, "wins": 13, "draws": 0, "losses": 2,
                "goals_for": 13, "goals_against": 13, "goal_diff": 0, "points": 26 },
  "computed": { "tournaments": 1, "games": 3,  "wins": 1,  "draws": 0, "losses": 2,
                "goals_for": 13, "goals_against": 13, "goal_diff": 0, "points": 2 },
  "corrections": { "tournaments": 6, "games": 20, "wins": 12 },
  "corrected_fields": ["games", "tournaments", "wins"],

  "created_at": "2026-08-23T…",
  "updated_at": "2026-08-25T…"
}
```

| Поле | Смысл |
|---|---|
| `stats` | Итог: расчёт по матчам плюс поправка. Это же уходит в публичный API |
| `computed` | Только по заведённым матчам |
| `corrections` | Сохранённые поправки. Нулей и `null` здесь не бывает |
| `corrected_fields` | Какие показатели имеют поправку |

---

## Игроки

Общий справочник. Номер и команда задаются не здесь, а в заявке на турнир.

| Метод | Путь | Прим. |
|---|---|---|
| `GET` | `/players` | `skip`, `limit`, `search` — подстрока ФИО, регистронезависимо |
| `POST` | `/players` | `{ full_name, birth_date?, position?, photo? }` |
| `PATCH` | `/players/{player_id}` | |
| `DELETE` | `/players/{player_id}` | `204`. Вся статистика игрока исчезнет каскадом |

`position` — одно из `вратарь`, `защитник`, `нападающий` либо `null`. Другое значение даёт
`422`.

---

## Турниры

| Метод | Путь |
|---|---|
| `GET` | `/tournaments` — `skip`, `limit` |
| `POST` | `/tournaments` |
| `PATCH` | `/tournaments/{tournament_id}` |
| `DELETE` | `/tournaments/{tournament_id}` · `/tournaments` |

| Поле | Тип | Прим. |
|---|---|---|
| `title` | string ≤ 512 | обязательно |
| `age_category` | string ≤ 32 | обязательно |
| `birth_year` | string ≤ 32 \| null | |
| `start_date` / `end_date` | date | обязательно; `end_date` не раньше `start_date` |
| `start_time` / `end_time` | `HH:MM` \| null | |
| `arena_id` | UUID | обязательно, арена должна существовать |
| `season` | string ≤ 16 \| null | Не задан — выводится из даты начала |
| `description` | string ≤ 4000 \| null | |
| `url` / `recordings_url` | string ≤ 1024 \| null | Положение и плейлист записей |
| `game_format` | string ≤ 16 \| null | «4-4» из шапки протокола |
| `period_minutes` | int 1…120 \| null | Из них считаются минуты в воротах |
| `periods_count` | int 1…10 \| null | Он же ограничивает период гола (`periods_count + 1`) |
| `position` | int 0…10000 | Порядок на сайте |
| `is_visible` | bool | `false` скрывает турнир и всю его статистику из публичного API |
| `teams` | массив `{ team_id, photo? }` | **Порядок важен** — он задаёт порядок команд |

**Про `teams`:** список полностью описывает состав участников. Команда, которой в списке
нет, из турнира убирается — но если у неё есть матчи или заявленные игроки, вернётся
`409` с перечислением таких команд. `photo` — общее фото состава именно на этом турнире.

---

## Заявка на турнир (состав)

Кто из справочника игроков заявлен за какую команду и под каким номером.

| Метод | Путь | Прим. |
|---|---|---|
| `GET` | `/tournaments/{id}/roster` | Вся заявка: по команде, затем по номеру |
| `POST` | `/tournaments/{id}/roster` | Массовое добавление |
| `PATCH` | `/tournaments/{id}/roster/{entry_id}` | `{ number }` |
| `DELETE` | `/tournaments/{id}/roster/{entry_id}` | `204` |

```json
{
  "team_id": "ffbcfc25-…",
  "players": [ { "player_id": "…", "number": 35 }, { "player_id": "…", "number": null } ]
}
```

Ответ — массив созданных записей:

```json
[ {
  "id": "8a32c530-…", "team_id": "ffbcfc25-…", "team_name": "Искра",
  "player_id": "3552e611-…", "full_name": "Трофимов Мирон",
  "birth_date": null, "position": null, "photo": null, "number": 2
} ]
```

- Уже заявленные игроки молча пропускаются — повторный запрос безопасен.
- Команда обязана участвовать в турнире, иначе `400`.
- Номер уникален внутри команды турнира: повтор — `409`. Пустой номер разрешён любому
  числу игроков.
- Один игрок может быть заявлен за **две команды одного турнира** — схема этого не
  запрещает. В списках игроков он тогда появится дважды.

---

## Матчи

| Метод | Путь |
|---|---|
| `GET` | `/tournaments/{id}/games` |
| `POST` | `/tournaments/{id}/games` |
| `GET` | `/games/{game_id}` |
| `PATCH` | `/games/{game_id}` |
| `DELETE` | `/games/{game_id}` — `204`, вместе с протоколом |

| Поле | Тип | Прим. |
|---|---|---|
| `team_a_id` / `team_b_id` | UUID | Обязательны при создании; обе команды должны участвовать в турнире, иначе `400`. Совпадают — `400` |
| `date` | date | обязательно |
| `time` | `HH:MM` \| null | |
| `score_a` / `score_b` | int 0…99 \| null | «Голы» из табло |
| `shots_a` / `shots_b` | int 0…999 \| null | «Броски» из табло |
| `video_url` | string ≤ 1024 \| null | |
| `scan` | string ≤ 1024 \| null | URL из `/uploads/game-scan` |
| `position` | int 0…10000 \| null | «МАТЧ №». Не задан при создании — берётся следующий |

`is_finished` **не принимается** — сервер ставит его сам, когда заполнены оба счёта.

**Смена команд у матча с заполненным протоколом отклоняется** (`409`): иначе строки
участия и голы остались бы от прежних составов. Проверяется факт смены, а не наличие поля
в запросе, — поэтому правка счёта, скана или даты проходит свободно.

---

## Протокол матча

Единственный путь записи статистики игроков.

### GET /api/admin/games/{game_id}/protocol

```jsonc
{
  "game": { /* объект матча, snake_case */ },
  "period_minutes": 15,
  "periods_count": 2,

  "stat_lines": [
    { "player_id": "…", "team_id": "…", "full_name": "Едигарев Роман", "number": 35,
      "position": "вратарь", "is_goalie": true,
      "goals": 0, "assists": 0, "points": 0,
      "goals_against": 8, "saves": 18 }
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

| Поле | Смысл |
|---|---|
| `goals_in_timeline_a/b` | Для сверки со счётом — кабинет подсвечивает расхождение |
| `goalie_ambiguous_team_ids` | Команды, где вратарей ноль или больше одного: вратарские за этот матч не начислены |
| `sort_order` | Порядок **в пределах матча**, а не номер строки бланка. У первого гола второй команды он может быть `2` |

### PUT /api/admin/games/{game_id}/protocol

Полная замена.

```jsonc
{
  "score_a": 1, "score_b": 8,
  "shots_a": 8, "shots_b": 26,

  "stat_lines": [
    { "player_id": "…", "team_id": "…", "is_goalie": true },
    { "player_id": "…", "team_id": "…", "is_goalie": false }
  ],

  "events": [
    { "team_id": "…", "period": 1, "time": "13:36",
      "player_id": "…", "assist1_player_id": "…", "assist2_player_id": null }
  ]
}
```

**Голы и передачи выводятся из `events`** и перезаписываются при каждом сохранении.
Прислать `goals`/`assists` в `stat_lines` нельзя — вернётся `422`. Это защита от
устаревшего клиента, который иначе молча обнулил бы цифры.

**Три состояния `events`:**

| Значение | Поведение |
|---|---|
| поле не передано | Таймлайн не трогаем, производные пересчитываем из того, что в базе |
| `[]` | Таймлайн очищаем, голы и передачи обнуляем |
| массив | Полная замена таймлайна |

**`time`** принимается как `MM:SS`, но терпит `1336`, `15м`, `2м30с`. Это время **внутри
периода**.

**Валидация** (любое нарушение — `422` с русским текстом, ничего не записывается):

- строки участия: команда — одна из двух в матче, игрок не повторяется, игрок заявлен
  в состав турнира за эту команду;
- время не больше длительности периода, период не больше `periods_count + 1`
  (последний — овертайм);
- автор и оба ассистента имеют строку участия **за ту же команду**;
- ассистент не равен автору и не дублируется, `assist2` без `assist1` отклоняется.

Ответ — тот же расширенный протокол, что у `GET`.

---

## Загрузка файлов

`multipart/form-data`, поле `file`. Ответ — `{"url": "/static/…"}`; этот URL кладётся
в соответствующее поле объекта.

| Путь | Куда | Лимит | Типы |
|---|---|---|---|
| `POST /uploads/team-logo` | `static/teams/` | 5 МБ | png, jpeg, webp, svg, gif |
| `POST /uploads/team-photo` | `static/team-photos/` | 5 МБ | те же |
| `POST /uploads/player-photo` | `static/player-photos/` | 5 МБ | те же |
| `POST /uploads/game-scan` | `static/protocols/` | **10 МБ** | те же + `application/pdf` |

Недопустимый тип — `400`, превышение размера — `413`. Имя файла заменяется на UUID,
исходное не сохраняется. Загрузка сама ничего не привязывает — URL нужно записать
`PATCH`-ом в объект.

```bash
curl -s -X POST https://api.timeofthestars-kids.ru/api/admin/uploads/game-scan \
  -H "Authorization: Bearer $TOKEN" -F 'file=@protocol.pdf'
```
