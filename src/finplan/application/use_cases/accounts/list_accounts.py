"""Use case `ListAccounts`: список неархивных счетов пользователя.

`docs/architecture.md`, раздел 6.1 — клавиатура выбора счёта в диалогах
`/expense` и `/income`.
"""

from __future__ import annotations

from finplan.application.dto.accounts import AccountDTO, AccountListDTO, ListAccountsQuery
from finplan.application.ports.uow import UnitOfWorkFactory


class ListAccounts:
    """Возвращает неархивные счета пользователя в порядке репозитория."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, query: ListAccountsQuery) -> AccountListDTO:
        async with self._uow_factory(query.user_id) as uow:
            accounts = await uow.accounts.list(query.user_id)
        return AccountListDTO(items=tuple(AccountDTO.from_entity(account) for account in accounts))
