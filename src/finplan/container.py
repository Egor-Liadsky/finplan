"""Композиция зависимостей — корень сборки процессов `bot`, `api` и `worker`.

`docs/architecture.md`, раздел 2.2, абзац «Зависимости хендлеры получают из
`Container`»: диспетчер aiogram кладёт контейнер в `workflow_data` под ключом
`container`, хендлер принимает его аргументом. Отдельной DI-библиотеки нет —
граф статичен и объектов на процесс десяток.

`build_container` не подключается к базе: `create_async_engine` и
`async_sessionmaker` не открывают соединение при создании, только при первом
запросе. Engine хранится в контейнере, а не только в замыкании фабрики
Unit of Work, чтобы `aclose()` могла его освободить при остановке процесса.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from finplan.application.ports.clock import Clock
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.application.use_cases.accounts.get_balances import GetBalances
from finplan.application.use_cases.accounts.list_accounts import ListAccounts
from finplan.application.use_cases.auth.find_user import FindUserByTelegramId
from finplan.application.use_cases.auth.register_user import RegisterUser
from finplan.application.use_cases.categories.list_categories import ListCategories
from finplan.application.use_cases.reports.period_summary import GetPeriodSummary
from finplan.application.use_cases.transactions.record_transaction import RecordTransaction
from finplan.application.use_cases.transactions.undo_last import UndoLastTransaction
from finplan.config import Settings
from finplan.infrastructure.clock import SystemClock
from finplan.infrastructure.db.engine import create_engine, create_sessionmaker
from finplan.infrastructure.db.queries.ledger import SqlAlchemyLedgerQueries
from finplan.infrastructure.db.uow import SqlAlchemyUnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class Container:
    """Граф зависимостей на один процесс: часы, Unit of Work и use case этапа 1."""

    clock: Clock
    uow_factory: UnitOfWorkFactory
    register_user: RegisterUser
    find_user: FindUserByTelegramId
    list_accounts: ListAccounts
    get_balances: GetBalances
    list_categories: ListCategories
    record_transaction: RecordTransaction
    undo_last: UndoLastTransaction
    period_summary: GetPeriodSummary
    engine: AsyncEngine

    async def aclose(self) -> None:
        """Освобождает engine БД. Вызывается один раз при остановке процесса."""
        await self.engine.dispose()


def build_container(settings: Settings) -> Container:
    """Собирает `Container` по `Settings`, не обращаясь к базе."""
    engine = create_engine(settings.database)
    sessionmaker = create_sessionmaker(engine)
    uow_factory = SqlAlchemyUnitOfWorkFactory(sessionmaker, SqlAlchemyLedgerQueries)
    clock: Clock = SystemClock()

    return Container(
        clock=clock,
        uow_factory=uow_factory,
        register_user=RegisterUser(uow_factory, clock),
        find_user=FindUserByTelegramId(uow_factory),
        list_accounts=ListAccounts(uow_factory),
        get_balances=GetBalances(uow_factory),
        list_categories=ListCategories(uow_factory),
        record_transaction=RecordTransaction(uow_factory, clock),
        undo_last=UndoLastTransaction(uow_factory, clock),
        period_summary=GetPeriodSummary(uow_factory, clock),
        engine=engine,
    )
