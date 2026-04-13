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
            "Новая запись:\n"
            f"Телефон: {phone}\n"
            f"ФИО родителя: {parent_name}\n"
            f"ФИО ребёнка: {child_name}\n"
            f"Возраст: {child_age}"
        )

    def _build_question_message(self, *, full_name: str, phone: str) -> str:
        return (
            "Новый вопрос:\n"
            f"ФИО: {full_name}\n"
            f"Телефон: {phone}"
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
