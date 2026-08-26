# Time of the Stars Kids — backend

Production-oriented асинхронный API на **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0 (async)** и **httpx** для VK. Есть **веб-кабинет** для администраторов (`/admin/`) и API для просмотра заявок без бота.

## Требования

- Python 3.11+
- PostgreSQL 14+ (в Docker — см. ниже)

## Быстрый старт (Docker)

1. Скопируйте переменные окружения:

   ```bash
   cp .env.example .env
   ```

2. Заполните в `.env` как минимум:

   - `VK_TOKEN` — токен VK с правом отправки сообщений
   - `JWT_SECRET` — случайная строка **не короче 32 символов**
   - `ADMIN_BOOTSTRAP_USERNAME` / `ADMIN_BOOTSTRAP_PASSWORD` — создадут **первого** админа, пока таблица `admin_users` пуста (в проде переменные лучше убрать после первого входа)
   - опционально `ADMIN_BOOTSTRAP_VK_USER_ID` — сразу привязать VK `user_id` к этому первому админу

   **Кому слать уведомления в VK** задаётся **в кабинете** (поле `vk_user_id` у каждого администратора в БД), а не списком в `.env`.

   **Важно для Docker Compose:** файл `.env` в корне проекта нужен и приложению, и **самому Compose** — он подставляет `${...}` в `docker-compose.yml`.

3. Запуск:

   ```bash
   docker compose up --build
   ```

4. Кабинет: <http://localhost:8000/admin/> — войдите и у каждого админа укажите **VK user_id** (или при создании нового админа).  
5. Документация OpenAPI: <http://localhost:8000/docs>

Перед стартом приложения выполняется `alembic upgrade head`.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`DATABASE_URL` **должен** быть вида `postgresql+asyncpg://...`.

## API

Полный справочник эндпоинтов — в папке [docs/](docs/):

| Документ | О чём |
|---|---|
| [docs/README.md](docs/README.md) | Соглашения: два контура, camelCase против snake_case, коды ошибок |
| [docs/public-api.md](docs/public-api.md) | Публичное API — 18 эндпоинтов: турниры, статистика, формы с сайта |
| [docs/admin-api.md](docs/admin-api.md) | API кабинета — 67 эндпоинтов: справочники, турниры, протоколы, загрузки |
| [docs/statistics.md](docs/statistics.md) | Как считается статистика и где она ведёт себя неочевидно |

Интерактивная схема живёт на самом сервисе: [`/docs`](https://api.timeofthestars-kids.ru/docs),
[`/redoc`](https://api.timeofthestars-kids.ru/redoc),
[`/openapi.json`](https://api.timeofthestars-kids.ru/openapi.json).

Коротко о делении:

- **публичный контур** — без авторизации, поля **camelCase**, читающие ручки отдают
  `Cache-Control: public, max-age=300`;
- **кабинет** — префикс `/api/admin`, `Authorization: Bearer <token>`, поля **snake_case**.

## Кабинет администратора

### Роли

- **`admin`** — полный доступ, включая вкладку **Пользователи** и `/api/admin/admins*`.
- **`viewer`** — всё остальное; `/api/admin/admins*` отвечает **403**.

Первый пользователь из bootstrap получает роль **`admin`**, новые создаются как
**`viewer`**. Последнего активного `admin` нельзя отключить или понизить.

### UI

**`/admin/`** — кабинет: Заявки · Услуги · Вопросы · Отзывы · Новости · Команды · Игроки ·
Арены · Турниры · Заявки на турнир · Профиль · Пользователи (только для `admin`).

**`/admin/tournament.html?id=<uuid>`** — экран одного турнира: составы команд с номерами,
матчи и редактор протокола, повторяющий раскладку бумажного бланка. Открывается кнопкой
«Статистика» в строке турнира.

### Уведомления в VK

О новых заявках, заявках на услуги, вопросах и заявках на турнир получает **каждый
активный** пользователь с заполненным `vk_user_id` (любая роль). Если не заполнен ни
у кого — VK не вызывается, заявка всё равно сохраняется.

## VK

Метод [`messages.send`](https://dev.vk.com/method/messages.send): в окружении хранится только **`VK_TOKEN`**. Список получателей собирается из **`admin_users.vk_user_id`** (активные пользователи).

Сообщения отправляются **по очереди** (мягче к лимитам VK). Ошибки VK обрабатываются с **async retry** для части кодов.

## Структура проекта

```
app/
  main.py
  api/
  core/       # config, logging, security
  db/
  models/
  schemas/
  services/
  clients/    # VK API
  repositories/
static/admin/ # UI кабинета (index.html — кабинет, tournament.html — статистика турнира)
alembic/
docs/         # справочник API и описание статистики
scripts/      # e2e_stats_check.py — сквозная проверка; load_tournament.py — загрузка протоколов
tests/        # unit-тесты арифметики статистики (без БД): pytest tests/
```

## Переменные окружения

См. [.env.example](.env.example).
