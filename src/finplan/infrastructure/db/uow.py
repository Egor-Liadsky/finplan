"""`SqlAlchemyUnitOfWork` и `SqlAlchemyUnitOfWorkFactory`.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции», и раздел 4.5 про установку `app.user_id` для RLS в начале
транзакции.

Реализацию протокола `LedgerQueries` этот модуль не импортирует напрямую из
пакета подзадачи 9b: она принадлежит параллельной подзадаче и попадёт сюда
через `ledger_factory`, подставляемую `container.py` (раздел 2.2: реализации
подставляются в `container.py`, `application` и то, что его обслуживает,
знает только протокол).
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import TYPE_CHECKING, Self
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from finplan.application.ports.repositories import (
    AccountRepository,
    CategoryRepository,
    LedgerQueries,
    TransactionRepository,
    UserRepository,
)
from finplan.application.ports.uow import UnitOfWork, UnitOfWorkFactory
from finplan.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from finplan.infrastructure.db.repositories.categories import SqlAlchemyCategoryRepository
from finplan.infrastructure.db.repositories.transactions import SqlAlchemyTransactionRepository
from finplan.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from finplan.infrastructure.db.rls import set_current_user


class SqlAlchemyUnitOfWork:
    """Одна транзакция use case поверх `AsyncSession`.

    Транзакция открывается лениво: `AsyncSession` начинает её на первом
    запросе (autobegin). Если `user_id` известен, этим первым запросом
    становится установка `app.user_id` в `__aenter__` — как того требует
    раздел 4.5. Если `user_id` — `None` (поиск пользователя по
    `telegram_id`), транзакция откроется на первом обращении к
    репозиторию, без `app.user_id`, и RLS не пропустит ни одной строки
    `users` — это ожидаемо для такого поиска (раздел 4.5).

    Повторный `commit()` в одном и том же экземпляре запрещён явно
    (`RuntimeError`), а не поддержан переустановкой `app.user_id`: раздел
    2.2 отводит `UnitOfWork` одну транзакцию на один вызов use case, а не
    цепочку транзакций в одном блоке `async with`. Молчаливая переустановка
    `app.user_id` после `commit()` спрятала бы это нарушение контракта;
    явное исключение вместо этого требует открыть новый `UnitOfWork` через
    фабрику для новой транзакции.
    """

    # Аннотации — типы протоколов, а не конкретных реализаций: `UnitOfWork`
    # объявляет эти атрибуты как `AccountRepository` и так далее, а мутируемый
    # атрибут протокола mypy сверяет инвариантно. Аннотация конкретным
    # `SqlAlchemyAccountRepository` не проходила бы `type[UnitOfWork] =
    # SqlAlchemyUnitOfWork` ниже, хотя каждый репозиторий сам по себе
    # протоколу соответствует (см. `_check` в его модуле).
    users: UserRepository
    accounts: AccountRepository
    categories: CategoryRepository
    transactions: TransactionRepository
    ledger: LedgerQueries

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        ledger_factory: Callable[[AsyncSession], LedgerQueries],
        user_id: UUID | None,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._ledger_factory = ledger_factory
        self._user_id = user_id
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> Self:
        session = self._sessionmaker()
        self._session = session
        if self._user_id is not None:
            await set_current_user(session, self._user_id)
        self.users = SqlAlchemyUserRepository(session)
        self.accounts = SqlAlchemyAccountRepository(session)
        self.categories = SqlAlchemyCategoryRepository(session)
        self.transactions = SqlAlchemyTransactionRepository(session)
        self.ledger = self._ledger_factory(session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            if not self._committed:
                await session.rollback()
        finally:
            await session.close()
            self._session = None

    async def commit(self) -> None:
        if self._committed:
            raise RuntimeError(
                "SqlAlchemyUnitOfWork.commit() уже вызывался в этом экземпляре: "
                "новая транзакция не переустановит app.user_id заново. "
                "Откройте новый UnitOfWork через фабрику для следующей транзакции."
            )
        assert self._session is not None, "commit() вызван до __aenter__"
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        assert self._session is not None, "rollback() вызван до __aenter__"
        await self._session.rollback()


class SqlAlchemyUnitOfWorkFactory:
    """Фабрика `SqlAlchemyUnitOfWork` от имени конкретного пользователя."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        ledger_factory: Callable[[AsyncSession], LedgerQueries],
    ) -> None:
        self._sessionmaker = sessionmaker
        self._ledger_factory = ledger_factory

    def __call__(self, user_id: UUID | None) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._sessionmaker, self._ledger_factory, user_id)


if TYPE_CHECKING:
    _check_uow: type[UnitOfWork] = SqlAlchemyUnitOfWork
    _check_factory: type[UnitOfWorkFactory] = SqlAlchemyUnitOfWorkFactory
