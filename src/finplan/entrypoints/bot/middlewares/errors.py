"""`ErrorMiddleware` — гарантированный ответ пользователю на любую ошибку.

`docs/architecture.md`, раздел 6.2, «Middleware», пункт 2, и раздел 12.2
«Обработка ошибок»: ошибки ввода, доменные ошибки и ошибки `application`
превращаются в текст из `formatters/errors.py`; остальные исключения
пишутся в лог с трейсом, а пользователь получает «Не удалось сохранить.
Попробуйте ещё раз. Код: <update_id>». Молчащий бот выглядит как сломанный,
поэтому отправка ответа обёрнута отдельным `try`: если отправить ответ не
удалось, это логируется, а исключение наружу не выпускается.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update

from finplan.application.errors import ApplicationError
from finplan.application.ports.repositories import DuplicateError
from finplan.domain.common.errors import DomainError
from finplan.entrypoints.bot.formatters.errors import error_message
from finplan.entrypoints.bot.parsers.quickinput import QuickInputError
from finplan.logging import get_logger

_logger = get_logger(__name__)

#: Классы, чей текст берётся из `error_message` (раздел 2.2, «Нарушение
#: уникального ключа...»: `DuplicateError` — не потомок `DomainError` или
#: `ApplicationError`, поэтому перечислен отдельно).
_KNOWN_ERRORS: tuple[type[Exception], ...] = (
    QuickInputError,
    DomainError,
    ApplicationError,
    DuplicateError,
)

_SYSTEM_ERROR_TEXT = "Не удалось сохранить. Попробуйте ещё раз. Код: {update_id}"


class ErrorMiddleware(BaseMiddleware):
    """Перехватывает исключения хендлеров и всегда отвечает пользователю.

    Регистрируется как `dp.update.outer_middleware`, второй в цепочке
    (раздел 6.2) — раньше `UserMiddleware`, потому что первое обращение к
    базе делает поиск пользователя, и недоступная база не должна оставлять
    бота молчащим.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        assert isinstance(event, Update)
        try:
            return await handler(event, data)
        except _KNOWN_ERRORS as exc:
            await _reply(event, error_message(exc))
        except Exception as exc:  # единственное место, где бот обязан ответить
            _logger.error("bot.unhandled_error", error=type(exc).__name__, exc_info=True)
            await _reply(event, _SYSTEM_ERROR_TEXT.format(update_id=event.update_id))
        return None


async def _reply(event: Update, text: str) -> None:
    try:
        if event.message is not None:
            await event.message.answer(text)
            return
        callback = event.callback_query
        if callback is not None:
            await callback.answer()
            if isinstance(callback.message, Message):
                await callback.message.answer(text)
    except Exception:  # отправка ответа не должна ронять апдейт
        _logger.error("bot.reply_failed", exc_info=True)
