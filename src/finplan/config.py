"""Конфигурация приложения.

Единая точка чтения переменных окружения — класс :class:`Settings` и
функция-точка доступа :func:`get_settings`. Источник истины по перечню
переменных, значениям по умолчанию и признакам обязательности —
``docs/architecture.md``, раздел 10.1.

Секции класса — деталь группировки внутри ``Settings``; имена переменных
окружения, которые читает каждое поле, совпадают с таблицей раздела 10.1
дословно, независимо от вложенности.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnv = Literal["local", "staging", "production"]
LogFormat = Literal["json", "console"]
TelegramMode = Literal["polling", "webhook"]
FxProvider = Literal["cbr", "none"]


def _split_comma_list(value: object) -> object:
    """Разбирает строку вида ``"a,b,c"`` в список строк без пустых элементов.

    Применяется как ``field_validator(mode="before")`` к полям-спискам,
    которые ``pydantic-settings`` иначе попытался бы прочитать как JSON.
    """
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class _SectionSettings(BaseSettings):
    """Общая база для секций ``Settings``: чтение ``.env``, регистр и лишние переменные."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class AppSettings(_SectionSettings):
    """Секция ``APP_*``."""

    env: AppEnv = Field(validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    base_url: str = Field(validation_alias="APP_BASE_URL")


class LogSettings(_SectionSettings):
    """Секция ``LOG_*``."""

    level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    format: LogFormat = Field(default="json", validation_alias="LOG_FORMAT")


class DatabaseSettings(_SectionSettings):
    """Секция ``DATABASE_*`` и ``WORKER_DATABASE_URL``.

    Значения подключения — ``SecretStr``, чтобы пароль не попадал в ``repr``
    и в логи; код, которому нужна строка подключения, получает её через
    :meth:`dsn` / :meth:`worker_dsn`.
    """

    url: SecretStr = Field(validation_alias="DATABASE_URL")
    pool_size: int = Field(default=10, validation_alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(default=5, validation_alias="DATABASE_MAX_OVERFLOW")
    echo: bool = Field(default=False, validation_alias="DATABASE_ECHO")
    worker_url: SecretStr | None = Field(default=None, validation_alias="WORKER_DATABASE_URL")

    @model_validator(mode="after")
    def _default_worker_url(self) -> DatabaseSettings:
        if self.worker_url is None:
            self.worker_url = self.url
        return self

    def dsn(self) -> str:
        """Строка подключения к основной БД."""
        return self.url.get_secret_value()

    def worker_dsn(self) -> str:
        """Строка подключения к БД для роли ``worker`` (с ``BYPASSRLS``)."""
        assert self.worker_url is not None
        return self.worker_url.get_secret_value()


class TelegramSettings(_SectionSettings):
    """Секция ``TELEGRAM_*``."""

    bot_token: SecretStr = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    mode: TelegramMode = Field(default="polling", validation_alias="TELEGRAM_MODE")
    webhook_url: str | None = Field(default=None, validation_alias="TELEGRAM_WEBHOOK_URL")
    webhook_path: str | None = Field(default=None, validation_alias="TELEGRAM_WEBHOOK_PATH")
    webhook_secret: SecretStr | None = Field(
        default=None, validation_alias="TELEGRAM_WEBHOOK_SECRET"
    )
    auth_max_age: int = Field(default=300, validation_alias="TELEGRAM_AUTH_MAX_AGE")

    @model_validator(mode="after")
    def _require_webhook_fields(self) -> TelegramSettings:
        if self.mode != "webhook":
            return self
        if not self.webhook_url:
            raise ValueError("TELEGRAM_WEBHOOK_URL is required when TELEGRAM_MODE=webhook")
        if not self.webhook_path:
            raise ValueError("TELEGRAM_WEBHOOK_PATH is required when TELEGRAM_MODE=webhook")
        if not self.webhook_secret:
            raise ValueError("TELEGRAM_WEBHOOK_SECRET is required when TELEGRAM_MODE=webhook")
        return self


class JwtSettings(_SectionSettings):
    """Секция ``JWT_*``."""

    secrets: Annotated[list[SecretStr], NoDecode] = Field(validation_alias="JWT_SECRETS")
    access_ttl: int = Field(default=900, validation_alias="JWT_ACCESS_TTL")

    @field_validator("secrets", mode="before")
    @classmethod
    def _parse_secrets(cls, value: object) -> object:
        parsed = _split_comma_list(value)
        if isinstance(parsed, list) and not parsed:
            raise ValueError("JWT_SECRETS must not be empty")
        return parsed

    def signing_secret(self) -> str:
        """Первый секрет списка — тот, которым подписываются новые токены."""
        return self.secrets[0].get_secret_value()


class FxSettings(_SectionSettings):
    """Секция ``FX_*``."""

    provider: FxProvider = Field(default="cbr", validation_alias="FX_PROVIDER")
    fetch_cron: str = Field(default="0 6 * * *", validation_alias="FX_FETCH_CRON")


class Settings(_SectionSettings):
    """Корневой объект конфигурации приложения.

    Секции (``app``, ``log``, ``database``, ``telegram``, ``jwt``, ``fx``)
    группируют переменные с общим префиксом имени; переменные без
    естественной группы — поля верхнего уровня.
    """

    # Секции ниже читают собственные обязательные переменные окружения при
    # вызове без аргументов; mypy не знает про этот механизм pydantic-settings
    # и считает `ClassName` несовместимым с `Callable[[], T]` из-за required
    # полей — подавляется точечно, поведение проверено тестами runtime.
    app: AppSettings = Field(default_factory=AppSettings)  # type: ignore[arg-type]
    log: LogSettings = Field(default_factory=LogSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore[arg-type]
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)  # type: ignore[arg-type]
    jwt: JwtSettings = Field(default_factory=JwtSettings)  # type: ignore[arg-type]
    fx: FxSettings = Field(default_factory=FxSettings)

    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    refresh_ttl: int = Field(default=2_592_000, validation_alias="REFRESH_TTL")
    login_ticket_ttl: int = Field(default=300, validation_alias="LOGIN_TICKET_TTL")
    cors_origins: Annotated[list[str], NoDecode] = Field(validation_alias="CORS_ORIGINS")
    default_base_currency: str = Field(default="RUB", validation_alias="DEFAULT_BASE_CURRENCY")
    default_timezone: str = Field(default="Europe/Moscow", validation_alias="DEFAULT_TIMEZONE")
    scheduler_enabled: bool = Field(default=True, validation_alias="SCHEDULER_ENABLED")
    sentry_dsn: str | None = Field(default=None, validation_alias="SENTRY_DSN")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        parsed = _split_comma_list(value)
        if isinstance(parsed, list) and not parsed:
            raise ValueError("CORS_ORIGINS must not be empty")
        return parsed


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает настройки приложения, читая окружение один раз за процесс."""
    return Settings()  # type: ignore[call-arg]
