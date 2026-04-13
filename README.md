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

## Публичное API

### `POST /appointments`

Тело запроса:

```json
{
  "phone": "+79991234567",
  "parent_name": "Иванова Мария Сергеевна",
  "child_name": "Иванов Пётр Иванович",
  "child_age": 7
}
```

Ответ `201`:

```json
{
  "id": "uuid",
  "status": "created"
}
```

Если у **ни одного** активного админа не задан `vk_user_id`, VK не вызывается — ответ всё равно `created` (уведомления в VK просто пропускаются, см. логи).

Если запись сохранена, но VK недоступен или вернул ошибку после ретраев:

```json
{
  "id": "uuid",
  "status": "created_notify_failed"
}
```

### `POST /questions`

Форма «задать вопрос» (ФИО и телефон):

```json
{
  "full_name": "Иванова Мария Сергеевна",
  "phone": "+79991234567"
}
```

Ответ `201`: `{ "id": "uuid", "status": "created" }`. Уведомления в VK уходят **тем же списком** `vk_user_id`, что и для заявок; при ошибке VK после ретраев: `status: "created_notify_failed"`. Если ни у кого не задан `vk_user_id`, VK не вызывается — ответ всё равно `created`.

### `GET /health`

Проверка живости сервиса.

## Кабинет администратора

### Роли

- **`admin`** — полный доступ: вкладка **Пользователи**, список/создание/редактирование учёток (`GET`/`POST`/`PATCH /api/admin/admins`).
- **`viewer`** — только **Заявки**, **Вопросы** и **Профиль** (свой `VK user_id`). Эндпоинты `/api/admin/admins*` возвращают **403**.

Первый пользователь из bootstrap и все уже существующие записи после миграции получают роль **`admin`**. Новые пользователи по умолчанию создаются как **`viewer`**, пока `admin` не выставит роль `admin` в форме.

### UI

**`/admin/`**: вкладки **Заявки** · **Вопросы** · **Профиль** (VK для всех) · **Пользователи** (только при `role === "admin"`). В «Пользователях»: таблица, создание, кнопка **Изменить** (логин, пароль, VK id, роль, активен).

### API (`Authorization: Bearer <token>`)

- `POST /api/admin/auth/login` — `{ "username", "password" }`
- `GET /api/admin/me` — `username`, `role`, `vk_user_id`
- `PATCH /api/admin/me/vk` — `{ "vk_user_id": <число> | null }`
- `GET /api/admin/appointments`, `GET /api/admin/questions` — любая активная роль
- `GET /api/admin/admins`, `POST /api/admin/admins`, `PATCH /api/admin/admins/{user_id}` — **только `admin`**
- `POST /api/admin/admins` — тело: `username`, `password`, `role` (`admin`|`viewer`), опционально `vk_user_id`
- `PATCH /api/admin/admins/{user_id}` — любое подмножество: `username`, `password`, `vk_user_id` (или `null`), `role`, `is_active`. Нельзя отключить или понизить **последнего** активного `admin`.

Уведомления VK о **новых заявках** и **новых вопросах**: **каждый активный** пользователь с заполненным **`vk_user_id`** (любая роль).

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
static/admin/ # UI кабинета
alembic/
```

## Переменные окружения

См. [.env.example](.env.example).
