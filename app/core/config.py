"""Application settings (Pydantic Settings v2)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        ...,
        alias="DATABASE_URL",
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )
    vk_token: str = Field(..., alias="VK_TOKEN", min_length=1)
    vk_read_token: str | None = Field(
        default=None,
        alias="VK_READ_TOKEN",
        description=(
            "Сервисный или user-токен для чтения публичных данных (board.getComments). "
            "Group-токен не подходит (ошибка VK 27). Если пусто — пробуем VK_TOKEN."
        ),
    )

    vk_api_version: str = Field(default="5.199", alias="VK_API_VERSION")
    http_timeout_seconds: float = Field(default=15.0, alias="HTTP_TIMEOUT_SECONDS")
    vk_retry_attempts: int = Field(default=3, ge=1, le=10, alias="VK_RETRY_ATTEMPTS")
    vk_retry_backoff_seconds: float = Field(
        default=0.5,
        ge=0.1,
        alias="VK_RETRY_BACKOFF_SECONDS",
    )
    vk_reviews_group_id: int = Field(
        default=125696800,
        ge=1,
        alias="VK_REVIEWS_GROUP_ID",
        description="ID сообщества VK, в котором лежит обсуждение с отзывами",
    )
    vk_reviews_topic_id: int = Field(
        default=56616420,
        ge=1,
        alias="VK_REVIEWS_TOPIC_ID",
        description="ID обсуждения (topic) с отзывами",
    )
    sqlalchemy_echo: bool = Field(default=False, alias="SQLALCHEMY_ECHO")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    jwt_secret: str = Field(..., alias="JWT_SECRET", min_length=32)
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, ge=5, le=60 * 24 * 30, alias="JWT_EXPIRE_MINUTES")

    admin_bootstrap_username: str | None = Field(default=None, alias="ADMIN_BOOTSTRAP_USERNAME")
    admin_bootstrap_password: str | None = Field(default=None, alias="ADMIN_BOOTSTRAP_PASSWORD")
    admin_bootstrap_vk_user_id: int | None = Field(
        default=None,
        alias="ADMIN_BOOTSTRAP_VK_USER_ID",
        description="VK user_id для первого админа (опционально)",
    )

    @model_validator(mode="after")
    def _bootstrap_password_required_with_username(self) -> Settings:
        if self.admin_bootstrap_username and not self.admin_bootstrap_password:
            msg = "ADMIN_BOOTSTRAP_PASSWORD is required when ADMIN_BOOTSTRAP_USERNAME is set"
            raise ValueError(msg)
        return self

    @field_validator("admin_bootstrap_vk_user_id")
    @classmethod
    def _bootstrap_vk_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            msg = "ADMIN_BOOTSTRAP_VK_USER_ID must be positive"
            raise ValueError(msg)
        return v

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, v: str) -> str:
        if "+asyncpg" not in v:
            msg = "DATABASE_URL must use asyncpg driver, e.g. postgresql+asyncpg://..."
            raise ValueError(msg)
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
