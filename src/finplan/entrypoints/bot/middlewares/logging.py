"""`LoggingMiddleware` — контекст логов на весь апдейт.

`docs/architecture.md`, раздел 6.2, «Middleware», пункт 1: `update_id` и
`telegram_id` в контекст логов, `service=bot`; контекст очищается после
апдейта. Раздел 12.1: `request_id` в боте играет `update_id`; полный текст
сообщения пользователя логировать запрещено, поэтому событие несёт только
тип апдейта.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from finplan.logging import bind_context, clear_context, get_logger

_logger = get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Привязывает `update_id` и `telegram_id` к контексту логов на апдейт.

    Регистрируется как `dp.update.outer_middleware` — первым в цепочке
    (раздел 6.2), чтобы контекст был доступен всем следующим middleware и
    хендлерам.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        assert isinstance(event, Update)
        user = data.get("event_from_user")
        bind_context(
            service="bot",
            request_id=event.update_id,
            user_id=user.id if user is not None else None,
        )
        try:
            _logger.info("bot.update_received", update_type=event.event_type)
            return await handler(event, data)
        finally:
            clear_context()
