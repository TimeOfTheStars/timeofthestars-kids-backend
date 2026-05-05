"""VK API client (messages.send) via httpx.AsyncClient."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

VK_METHOD_URL = "https://api.vk.com/method/messages.send"
VK_BOARD_GET_COMMENTS_URL = "https://api.vk.com/method/board.getComments"
VK_WALL_GET_BY_ID_URL = "https://api.vk.com/method/wall.getById"

# board.getComments отдаёт максимум 100 за раз.
_VK_BOARD_PAGE_SIZE = 100
_VK_BOARD_MAX_PAGES = 50  # 5000 комментариев — более чем достаточно

# VK error codes that are often transient; safe to retry briefly.
_RETRY_VK_ERROR_CODES: frozenset[int] = frozenset({6, 10})


class VKAPIError(Exception):
    """VK API returned error object in JSON body."""

    def __init__(self, error_code: int, error_msg: str, *, user_id: int | None = None) -> None:
        self.error_code = error_code
        self.error_msg = error_msg
        self.user_id = user_id
        suffix = f" (user_id={user_id})" if user_id is not None else ""
        super().__init__(f"VK API error {error_code}: {error_msg}{suffix}")


class VKClient:
    """Thin async wrapper around messages.send."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http_client
        self._settings = settings

    def _build_appointment_message(
        self,
        *,
        phone: str,
        parent_name: str,
        child_name: str,
        child_age: int,
    ) -> str:
        return (
            "📩 Новая запись:\n"
            f"📞 Телефон: {phone}\n"
            f"🧑‍🧒 ФИО родителя: {parent_name}\n"
            f"🧒 ФИО ребёнка: {child_name}\n"
            f"🗓️ Возраст: {child_age}"
        )

    def _build_question_message(self, *, full_name: str, phone: str) -> str:
        return (
            "❓ Новый вопрос:\n"
            f"👤 ФИО: {full_name}\n"
            f"📞 Телефон: {phone}"
        )

    def _build_service_request_message(
        self,
        *,
        phone: str,
        parent_name: str,
        child_name: str,
        child_age: int,
        service: str,
    ) -> str:
        return (
            "📋 Новая заявка на услугу:\n"
            f"🧾 Услуга: {service}\n"
            f"📞 Телефон: {phone}\n"
            f"🧑‍🧒 ФИО родителя: {parent_name}\n"
            f"🧒 ФИО ребёнка: {child_name}\n"
            f"🗓️ Возраст: {child_age}"
        )

    async def _notify_recipients(self, *, message: str, recipient_user_ids: list[int]) -> None:
        if not recipient_user_ids:
            return
        for user_id in recipient_user_ids:
            await self._send_to_user_with_retry(user_id=user_id, message=message)

    async def _messages_send(self, *, user_id: int, message: str) -> None:
        params: dict[str, Any] = {
            "access_token": self._settings.vk_token,
            "v": self._settings.vk_api_version,
            "user_id": user_id,
            "message": message,
            "random_id": secrets.randbelow(2**31),
        }

        response = await self._http.get(VK_METHOD_URL, params=params)
        response.raise_for_status()

        payload = response.json()
        if "error" in payload:
            err = payload["error"]
            code = int(err.get("error_code", 0))
            msg = str(err.get("error_msg", "unknown"))
            raise VKAPIError(code, msg, user_id=user_id)

        if "response" not in payload:
            raise VKAPIError(0, "unexpected VK response shape", user_id=user_id)

    async def _send_to_user_with_retry(self, *, user_id: int, message: str) -> None:
        attempts = self._settings.vk_retry_attempts
        backoff = self._settings.vk_retry_backoff_seconds

        for attempt in range(1, attempts + 1):
            try:
                await self._messages_send(user_id=user_id, message=message)
                return
            except VKAPIError as exc:
                if exc.error_code not in _RETRY_VK_ERROR_CODES or attempt >= attempts:
                    logger.warning(
                        "VK messages.send failed",
                        extra={
                            "vk_error_code": exc.error_code,
                            "user_id": user_id,
                            "attempt": attempt,
                            "max_attempts": attempts,
                        },
                    )
                    raise
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt >= attempts:
                    logger.exception(
                        "VK transport error after retries",
                        extra={"attempt": attempt, "user_id": user_id},
                    )
                    raise
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status < 500 or attempt >= attempts:
                    logger.warning(
                        "VK HTTP error",
                        extra={"status_code": status, "attempt": attempt, "user_id": user_id},
                    )
                    raise
            delay = backoff * (2 ** (attempt - 1))
            logger.info(
                "Retrying VK messages.send",
                extra={"attempt": attempt, "sleep_s": delay, "user_id": user_id},
            )
            await asyncio.sleep(delay)

        raise RuntimeError("VKClient._send_to_user_with_retry: retry loop exited unexpectedly")

    async def notify_new_appointment(
        self,
        *,
        phone: str,
        parent_name: str,
        child_name: str,
        child_age: int,
        recipient_user_ids: list[int],
    ) -> None:
        """Отправить уведомление о записи каждому VK user_id (последовательно)."""
        text = self._build_appointment_message(
            phone=phone,
            parent_name=parent_name,
            child_name=child_name,
            child_age=child_age,
        )
        await self._notify_recipients(message=text, recipient_user_ids=recipient_user_ids)

    async def notify_new_question(
        self,
        *,
        full_name: str,
        phone: str,
        recipient_user_ids: list[int],
    ) -> None:
        """Отправить уведомление о вопросе с формы (те же получатели, что и для заявок)."""
        text = self._build_question_message(full_name=full_name, phone=phone)
        await self._notify_recipients(message=text, recipient_user_ids=recipient_user_ids)

    async def fetch_topic_comments(
        self,
        *,
        group_id: int,
        topic_id: int,
    ) -> list[dict[str, Any]]:
        """Стянуть все комментарии обсуждения с автором (имя + фото).

        Возвращает список словарей вида:
            {"comment_id": int, "text": str, "author_name": str, "author_photo_url": str | None}
        Комментарии от групп (from_id < 0) пропускаются.
        """
        items: list[dict[str, Any]] = []
        profiles_by_id: dict[int, dict[str, Any]] = {}

        offset = 0
        for _ in range(_VK_BOARD_MAX_PAGES):
            page = await self._board_get_comments_page(
                group_id=group_id,
                topic_id=topic_id,
                offset=offset,
                count=_VK_BOARD_PAGE_SIZE,
            )
            page_items = page.get("items") or []
            for prof in page.get("profiles") or []:
                pid = prof.get("id")
                if isinstance(pid, int):
                    profiles_by_id[pid] = prof
            if not page_items:
                break
            items.extend(page_items)
            if len(page_items) < _VK_BOARD_PAGE_SIZE:
                break
            offset += _VK_BOARD_PAGE_SIZE

        out: list[dict[str, Any]] = []
        for it in items:
            cid = it.get("id")
            from_id = it.get("from_id")
            text = (it.get("text") or "").strip()
            if not isinstance(cid, int) or not isinstance(from_id, int):
                continue
            if from_id <= 0:
                # комментарий от имени группы — для отзывов не годится
                continue
            prof = profiles_by_id.get(from_id) or {}
            first = (prof.get("first_name") or "").strip()
            last = (prof.get("last_name") or "").strip()
            full_name = " ".join(p for p in (first, last) if p) or "Гость"
            photo = (
                prof.get("photo_max_orig")
                or prof.get("photo_max")
                or prof.get("photo_400_orig")
                or prof.get("photo_200")
                or prof.get("photo_100")
            )
            out.append(
                {
                    "comment_id": cid,
                    "text": text,
                    "author_name": full_name,
                    "author_photo_url": photo if isinstance(photo, str) and photo else None,
                },
            )
        return out

    async def _board_get_comments_page(
        self,
        *,
        group_id: int,
        topic_id: int,
        offset: int,
        count: int,
    ) -> dict[str, Any]:
        # board.getComments требует user- или сервисный токен; group-токен даёт VK error 27.
        read_token = self._settings.vk_read_token or self._settings.vk_token
        params: dict[str, Any] = {
            "access_token": read_token,
            "v": self._settings.vk_api_version,
            "group_id": group_id,
            "topic_id": topic_id,
            "offset": offset,
            "count": count,
            "need_likes": 0,
            "extended": 1,
            "sort": "asc",
            "lang": "ru",
            "fields": "photo_200,photo_max,photo_max_orig,photo_400_orig",
        }
        attempts = self._settings.vk_retry_attempts
        backoff = self._settings.vk_retry_backoff_seconds

        for attempt in range(1, attempts + 1):
            try:
                response = await self._http.get(VK_BOARD_GET_COMMENTS_URL, params=params)
                response.raise_for_status()
                payload = response.json()
                if "error" in payload:
                    err = payload["error"]
                    code = int(err.get("error_code", 0))
                    msg = str(err.get("error_msg", "unknown"))
                    if code in _RETRY_VK_ERROR_CODES and attempt < attempts:
                        await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                        continue
                    raise VKAPIError(code, msg)
                resp = payload.get("response")
                if not isinstance(resp, dict):
                    raise VKAPIError(0, "unexpected VK response shape")
                return resp
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt >= attempts:
                    logger.exception(
                        "VK board.getComments transport error",
                        extra={"attempt": attempt, "topic_id": topic_id},
                    )
                    raise
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code < 500 or attempt >= attempts:
                    logger.warning(
                        "VK board.getComments HTTP error",
                        extra={"status_code": status_code, "attempt": attempt},
                    )
                    raise
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))

        raise RuntimeError("VKClient._board_get_comments_page: retry loop exited unexpectedly")

    async def fetch_wall_post(
        self,
        *,
        owner_id: int,
        post_id: int,
    ) -> dict[str, Any] | None:
        """Стянуть один пост со стены (wall.getById).

        Возвращает {"text": str, "image": str | None} или None, если пост недоступен.
        Если у поста нет картинки/текста — пробуем взять из repost (copy_history).
        """
        read_token = self._settings.vk_read_token or self._settings.vk_token
        params: dict[str, Any] = {
            "access_token": read_token,
            "v": self._settings.vk_api_version,
            "posts": f"{owner_id}_{post_id}",
            "extended": 0,
            "lang": "ru",
        }
        attempts = self._settings.vk_retry_attempts
        backoff = self._settings.vk_retry_backoff_seconds

        for attempt in range(1, attempts + 1):
            try:
                response = await self._http.get(VK_WALL_GET_BY_ID_URL, params=params)
                response.raise_for_status()
                payload = response.json()
                if "error" in payload:
                    err = payload["error"]
                    code = int(err.get("error_code", 0))
                    msg = str(err.get("error_msg", "unknown"))
                    if code in _RETRY_VK_ERROR_CODES and attempt < attempts:
                        await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                        continue
                    raise VKAPIError(code, msg)
                # VK может вернуть и {"response": [post, ...]} и {"response": {"items": [...]}}.
                resp = payload.get("response")
                if isinstance(resp, dict):
                    items = resp.get("items") or []
                elif isinstance(resp, list):
                    items = resp
                else:
                    items = []
                if not items:
                    return None
                post = items[0]
                if not isinstance(post, dict):
                    return None
                return {
                    "text": _extract_post_text(post),
                    "image": _extract_post_image(post),
                }
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt >= attempts:
                    logger.exception(
                        "VK wall.getById transport error",
                        extra={"attempt": attempt, "owner_id": owner_id, "post_id": post_id},
                    )
                    raise
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code < 500 or attempt >= attempts:
                    logger.warning(
                        "VK wall.getById HTTP error",
                        extra={"status_code": status_code, "attempt": attempt},
                    )
                    raise
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))

        raise RuntimeError("VKClient.fetch_wall_post: retry loop exited unexpectedly")

    async def notify_new_service_request(
        self,
        *,
        phone: str,
        parent_name: str,
        child_name: str,
        child_age: int,
        service: str,
        recipient_user_ids: list[int],
    ) -> None:
        """Уведомление о заявке на услугу (те же VK user_id, что для записей и вопросов)."""
        text = self._build_service_request_message(
            phone=phone,
            parent_name=parent_name,
            child_name=child_name,
            child_age=child_age,
            service=service,
        )
        await self._notify_recipients(message=text, recipient_user_ids=recipient_user_ids)


def _extract_post_text(post: dict[str, Any]) -> str:
    """Достать текст поста; если основной пуст и есть репост — взять из copy_history."""
    text = (post.get("text") or "").strip()
    if text:
        return text
    for repost in post.get("copy_history") or []:
        if isinstance(repost, dict):
            t = (repost.get("text") or "").strip()
            if t:
                return t
    return ""


def _extract_post_image(post: dict[str, Any]) -> str | None:
    """Найти первое прикреплённое фото. Если в основном посте нет — посмотреть repost."""
    photo = _photo_from_attachments(post.get("attachments"))
    if photo:
        return photo
    for repost in post.get("copy_history") or []:
        if isinstance(repost, dict):
            photo = _photo_from_attachments(repost.get("attachments"))
            if photo:
                return photo
    return None


def _photo_from_attachments(attachments: Any) -> str | None:
    if not isinstance(attachments, list):
        return None
    for att in attachments:
        if not isinstance(att, dict) or att.get("type") != "photo":
            continue
        photo = att.get("photo")
        if not isinstance(photo, dict):
            continue
        sizes = photo.get("sizes")
        if not isinstance(sizes, list) or not sizes:
            continue
        def _area(s: Any) -> int:
            if not isinstance(s, dict):
                return 0
            return int(s.get("width") or 0) * int(s.get("height") or 0)
        best = max(sizes, key=_area)
        if isinstance(best, dict):
            url_value = best.get("url")
            if isinstance(url_value, str) and url_value:
                return url_value
    return None
