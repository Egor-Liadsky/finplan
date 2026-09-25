"""Порт `UnitOfWork`: транзакционная граница use case.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции», и раздел 4.5 про `SET LOCAL app.user_id` для RLS.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from finplan.application.ports.repositories import (
    AccountRepository,
    CategoryRepository,
    LedgerQueries,
    TransactionRepository,
    UserRepository,
)


class UnitOfWork(Protocol):
    """Одна транзакция use case: доступ к репозиториям и управление коммитом."""

    users: UserRepository
    accounts: AccountRepository
    categories: CategoryRepository
    transactions: TransactionRepository
    ledger: LedgerQueries

    async def __aenter__(self) -> Self:
        """Открывает транзакцию и возвращает себя для `async with`."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Откатывает транзакцию, если блок завершился без явного `commit`."""
        ...

    async def commit(self) -> None:
        """Фиксирует изменения текущей транзакции."""
        ...

    async def rollback(self) -> None:
        """Откатывает изменения текущей транзакции явно."""
        ...


class UnitOfWorkFactory(Protocol):
    """Фабрика `UnitOfWork` от имени конкретного пользователя."""

    def __call__(self, user_id: UUID | None) -> UnitOfWork:
        """Создаёт `UnitOfWork` для `user_id`.

        Реализация выставит `app.user_id` для RLS (раздел 4.5). `None`
        допустим только для поиска пользователя по `telegram_id`, пока его
        `id` ещё неизвестен.
        """
        ...
