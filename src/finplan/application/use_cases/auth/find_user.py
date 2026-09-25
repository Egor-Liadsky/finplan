"""Use case поиска пользователя по `telegram_id`.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»: фабрика `UnitOfWorkFactory` вызывается с `None`, потому что
`id` пользователя ещё неизвестен. Вызывающая сторона — `UserMiddleware`.
"""

from __future__ import annotations

from finplan.application.dto.auth import FindUserByTelegramIdQuery, UserDTO
from finplan.application.ports.uow import UnitOfWorkFactory


class FindUserByTelegramId:
    """Ищет пользователя по `telegram_id`, ничего не изменяя."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, query: FindUserByTelegramIdQuery) -> UserDTO | None:
        async with self._uow_factory(None) as uow:
            user = await uow.users.get_by_telegram_id(query.telegram_id)
        return UserDTO.from_entity(user) if user is not None else None
