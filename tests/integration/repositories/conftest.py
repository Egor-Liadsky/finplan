"""Фикстуры интеграционных тестов репозиториев и Unit of Work.

`docs/architecture.md`, раздел 11.1: репозитории проверяются против реальной
PostgreSQL, а состояние между тестами откатывается вложенной транзакцией.
Раздел 4.5: приложение подключается ролью `finplan_app` (`LOGIN
NOBYPASSRLS`), под которой действует RLS — этим она отличается от
`db_session` из `tests/conftest.py`, которая работает под владельцем схемы
и политики RLS обходит.

**Почему одна внешняя транзакция на тест, а не по одной на пользователя.**
`SqlAlchemyUnitOfWork.commit()` — это не `COMMIT` уровня PostgreSQL, а
`RELEASE SAVEPOINT` внутри внешней транзакции соединения (`async_sessionmaker
(bind=connection, join_transaction_mode="create_savepoint")`): сама внешняя
транзакция не коммитится никогда, только откатывается в конце теста — так
данные никогда не долетают до реальной таблицы, что нужно, чтобы тест не
портил состояние для соседних тестов. Отсюда следствие: если данные
пользователя A записываются на одном соединении/внешней транзакции, а
пользователь B читает с другого соединения, PostgreSQL с уровнем изоляции
`READ COMMITTED` не покажет B данные A вообще — они не закоммичены на уровне
базы. Тест изоляции тогда проходил бы даже при полностью сломанной или
отсутствующей RLS-политике и явном `WHERE user_id = ...` в репозитории:
причина «не видно» была бы не в правильно работающей защите, а в том, что
данных для чтения ещё физически нет. Поэтому все `UnitOfWork` внутри одного
теста — владельца данных и «соседа» — открываются на одном и том же
`app_connection`/`uow_factory`: строка, вставленная и закоммиченная (в
смысле `RELEASE SAVEPOINT`) от имени A, реально видна на этом соединении, и
тест проверяет, что её не отдаёт ни явный фильтр репозитория, ни политика
RLS — именно то поведение, которое `TestTenantIsolation` обязан ловить
(раздел 11.4).

**Подводный камень `app.user_id` и как он устранён.** `SET LOCAL`/
``set_config(..., true)`` живёт до конца *внешней* транзакции соединения, а
не до конца `SAVEPOINT`. Когда `SqlAlchemyUnitOfWork` пользователя A
вызывает `commit()` (= `RELEASE SAVEPOINT`), значение `app.user_id = A`,
выставленное внутри этого `SAVEPOINT`, не откатывается и остаётся видимым в
оставшейся открытой внешней транзакции соединения. Для следующего
`UnitOfWork` с известным `user_id` (в том числе «соседа» B) это неопасно:
`SqlAlchemyUnitOfWork.__aenter__` сам выполняет `set_config('app.user_id',
str(user_id), true)` первым запросом своей новой `SAVEPOINT`, и это явно
перекрывает всё, что было выставлено раньше в той же внешней транзакции —
поэтому `uow_factory(user_b.id)` после `uow_factory(user_a.id)` всегда
корректно видит только B. Опасен только `UnitOfWork` с `user_id=None`
(поиск пользователя по `telegram_id` до того, как он известен, раздел 4.5):
`__aenter__` в этом случае `app.user_id` не трогает вовсе, и такой `UnitOfWork`
унаследует значение, оставшееся от предыдущего пользователя, вместо
ожидаемого «не задано». Единственный такой сценарий в этих тестах —
`get_by_telegram_id`, которая всё равно идёт через функцию `SECURITY
DEFINER` и RLS/`app.user_id` не читает, поэтому унаследованное значение не
меняет результат этой конкретной проверки. Тем не менее фикстура
`reset_app_user_id` даёт тестам явный, не полагающийся на это совпадение
способ обнулить `app.user_id` перед открытием `UnitOfWork` без пользователя
— решение «сбросом значения в фикстуре» из задания.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    async_sessionmaker,
    create_async_engine,
)

from finplan.domain.common.currency import RUB, Currency
from finplan.domain.common.money import Money
from finplan.domain.entities.account import Account, AccountType
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind, TransactionStatus
from finplan.domain.entities.user import User
from finplan.infrastructure.db.queries.ledger import SqlAlchemyLedgerQueries
from finplan.infrastructure.db.uow import SqlAlchemyUnitOfWorkFactory

_MOSCOW = ZoneInfo("Europe/Moscow")


@pytest_asyncio.fixture
async def app_connection(app_database_url: str) -> AsyncIterator[AsyncConnection]:
    """Соединение под `finplan_app` со своей внешней транзакцией.

    Внешняя транзакция никогда не коммитится — только откатывается при
    завершении фикстуры, как `db_session` в `tests/conftest.py`, но здесь
    под ролью `finplan_app`, а не владельцем схемы. Доступно тестам
    напрямую — например, чтобы сверить значение столбца прямым SQL в той же
    транзакции, что и запись через репозиторий.
    """
    engine = create_async_engine(app_database_url)
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            try:
                yield connection
            finally:
                await outer_transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
def uow_factory(app_connection: AsyncConnection) -> SqlAlchemyUnitOfWorkFactory:
    """Фабрика `UnitOfWork`: все её экземпляры делят одну внешнюю транзакцию.

    См. докстринг модуля: владелец данных и «сосед» в тестах изоляции
    обязаны открывать `UnitOfWork` через одну и ту же фабрику/соединение.
    """
    sessionmaker = async_sessionmaker(
        bind=app_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    return SqlAlchemyUnitOfWorkFactory(sessionmaker, SqlAlchemyLedgerQueries)


@pytest.fixture
def reset_app_user_id(app_connection: AsyncConnection) -> Callable[[], Awaitable[None]]:
    """Явно обнуляет `app.user_id` на `app_connection` (см. докстринг модуля).

    Нужна перед `uow_factory(None)`, если до этого в той же внешней
    транзакции уже коммитился `UnitOfWork` с настоящим `user_id`: без
    сброса RLS-политика видела бы то значение по инерции, а не «не
    задано», как в реальном сценарии поиска пользователя по `telegram_id`.
    """

    async def _reset() -> None:
        await app_connection.execute(text("SELECT set_config('app.user_id', '', true)"))

    return _reset


# --- Построение доменных сущностей с осмысленными значениями по умолчанию.
#
# Фикстуры-фабрики, а не обычные функции модуля: файлы `tests/` не образуют
# импортируемый пакет (раздел 2.1 дерева каталогов не требует `__init__.py`),
# `import tests....conftest` из отдельного файла теста падает
# `ModuleNotFoundError` под `--import-mode=prepend` — тот же приём, что у
# `alembic_runner` в `tests/conftest.py`.


@pytest.fixture
def make_user() -> Callable[..., User]:
    def _make(**overrides: Any) -> User:
        defaults: dict[str, Any] = {
            "id": uuid4(),
            "telegram_id": uuid4().int % 1_000_000_000,
            "username": "tester",
            "first_name": "Тест",
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "base_currency": RUB,
            "timezone": "Europe/Moscow",
            "locale": "ru",
            "is_active": True,
        }
        defaults.update(overrides)
        return User(**defaults)

    return _make


@pytest.fixture
def make_account() -> Callable[..., Account]:
    def _make(*, user_id: UUID, **overrides: Any) -> Account:
        currency: Currency = overrides.get("currency", RUB)
        defaults: dict[str, Any] = {
            "id": uuid4(),
            "user_id": user_id,
            "name": f"Счёт {uuid4().hex[:8]}",
            "type": AccountType.CASH,
            "currency": currency,
            "opening_balance": Money(amount=Decimal("1000.0000"), currency=currency),
            "opened_at": date(2026, 1, 1),
            "is_valuated": False,
            "include_in_networth": True,
            "is_archived": False,
        }
        defaults.update(overrides)
        return Account(**defaults)

    return _make


@pytest.fixture
def make_category() -> Callable[..., Category]:
    def _make(
        *,
        user_id: UUID,
        kind: CategoryKind = CategoryKind.EXPENSE,
        slug: str | None = None,
        **overrides: Any,
    ) -> Category:
        category = Category.new_root(
            id=uuid4(),
            user_id=user_id,
            kind=kind,
            slug=slug or f"cat_{uuid4().hex[:8]}",
            name="Категория",
        )
        if overrides:
            category = replace(category, **overrides)
        return category

    return _make


@pytest.fixture
def make_transaction() -> Callable[..., Transaction]:
    def _make(
        *,
        user_id: UUID,
        account_id: UUID,
        category_id: UUID | None,
        kind: TransactionKind = TransactionKind.EXPENSE,
        status: TransactionStatus = TransactionStatus.POSTED,
        amount: Decimal = Decimal("100.0000"),
        currency: Currency = RUB,
        occurred_at: datetime | None = None,
        timezone: ZoneInfo = _MOSCOW,
        source: str = "bot",
        **overrides: Any,
    ) -> Transaction:
        moment = occurred_at or datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        defaults: dict[str, Any] = {
            "id": uuid4(),
            "user_id": user_id,
            "kind": kind,
            "status": status,
            "amount": Money(amount=amount, currency=currency),
            "account_id": account_id,
            "category_id": category_id,
            "occurred_at": moment,
            "timezone": timezone,
            "base_amount": amount,
            "base_currency": currency,
            "base_rate": Decimal("1"),
            "source": source,
            "created_at": moment,
            "now": moment,
        }
        defaults.update(overrides)
        return Transaction.new(**defaults)

    return _make
