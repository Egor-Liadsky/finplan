"""`UserMiddleware` — загрузка пользователя по `telegram_id` перед хендлером.

`docs/architecture.md`, раздел 6.2, «Middleware», пункт 4, и абзац
«Регистрация»: внешний middleware роутера `registered` для сообщений и
нажатий кнопок. Незарегистрированный пользователь получает «Нажмите
/start» без передачи апдейта дальше; иначе хендлер получает `UserDTO` в
`data["user"]` гарантированно, без проверки на `None`.

Пользователь ищется вызовом use case `container.find_user` — не напрямую
через репозиторий (раздел 2.2, «Контракт портов и граница транзакции»).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from finplan.application.dto.auth import FindUserByTelegramIdQuery
from finplan.container import Container

_PROMPT_TEXT = "Нажмите /start"


class UserMiddleware(BaseMiddleware):
    """Подставляет `user` в `data` или останавливает апдейт подсказкой."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        assert isinstance(event, Message | CallbackQuery)
        container: Container = data["container"]

        telegram_id = event.from_user.id if event.from_user else None
        user = (
            await container.find_user(FindUserByTelegramIdQuery(telegram_id=telegram_id))
            if telegram_id is not None
            else None
        )
        if user is None:
            await _prompt(event)
            return None

        data["user"] = user
        return await handler(event, data)


async def _prompt(event: Message | CallbackQuery) -> None:
    if isinstance(event, Message):
        await event.answer(_PROMPT_TEXT)
    else:
        await event.answer(_PROMPT_TEXT, show_alert=True)
