"""Настройка структурного логирования поверх ``structlog`` и stdlib ``logging``.

Формат и уровень читаются из :class:`finplan.config.Settings` (раздел
`docs/architecture.md`, 12.1). Стандартный ``logging`` подключён к тому же
конвейеру, чтобы записи ``uvicorn``, ``sqlalchemy`` и ``aiogram`` выходили в
том же формате, что и записи самого приложения.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from pydantic import SecretBytes, SecretStr

from finplan.config import Settings

_TIMESTAMPER = structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp")


def _redact_secrets(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Заменяет значения ``SecretStr``/``SecretBytes`` заглушкой перед выводом.

    Секреты (`TELEGRAM_BOT_TOKEN`, `JWT_SECRETS`, пароль БД) хранятся в
    `Settings` как `SecretStr` и не должны попасть в лог, даже если объект
    настроек по ошибке передан в событие целиком.
    """
    for key, value in list(event_dict.items()):
        if isinstance(value, SecretStr | SecretBytes):
            event_dict[key] = "***"
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Настраивает ``structlog`` и корневой ``logging`` по ``settings.log``.

    ``LOG_FORMAT=json`` — вывод через :class:`structlog.processors.JSONRenderer`;
    ``LOG_FORMAT=console`` — через цветной :class:`structlog.dev.ConsoleRenderer`.
    Уровень берётся из ``LOG_LEVEL``. Каждая запись содержит ``timestamp`` в
    ISO 8601 UTC, ``level`` и имя логгера (``logger``).
    """
    level = getattr(logging, settings.log.level.upper(), logging.INFO)

    renderer: structlog.types.Processor
    if settings.log.format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        _TIMESTAMPER,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _redact_secrets,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Возвращает структурный логгер, привязанный к текущему контексту."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger


def bind_context(**fields: Any) -> None:
    """Привязывает поля (``request_id``, ``user_id``, ``run_id`` и т. п.) к
    текущему контексту исполнения — они попадут во все записи до вызова
    :func:`clear_context`. Точки входа вызывают это на входящий запрос или
    апдейт.
    """
    structlog.contextvars.bind_contextvars(**fields)


def clear_context() -> None:
    """Очищает контекст, привязанный :func:`bind_context`."""
    structlog.contextvars.clear_contextvars()
