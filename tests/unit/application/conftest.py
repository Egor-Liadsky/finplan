"""Общие фикстуры модульных тестов use case: in-memory порты и фабрики данных.

`docs/architecture.md`, раздел 11.1 «Модульные с заглушками». Реализации
портов лежат в `fakes.py` этого же каталога; фабрики доменных объектов ниже
собирают валидные по умолчанию `User`/`Account`/`Category`/`Transaction`,
чтобы каждый тест переопределял только то поле, которое действительно
проверяет — тот же приём, что в `tests/unit/domain/test_transaction.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fakes import FakeUnitOfWorkFactory, FixedClock

from finplan.application.ports.clock import Clock
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.common.currency import RUB, Currency
from finplan.domain.common.money import Money
from finplan.domain.entities.account import Account, AccountType
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind, TransactionStatus
from finplan.domain.entities.user import User

#: Момент времени, который отдаёт `clock` по умолчанию во всех тестах.
NOW = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)

_telegram_id_counter = iter(range(1, 10**9))


@pytest.fixture
def clock() -> FixedClock:
    """`Clock` с фиксированным `NOW`; тест может сдвинуть время через `.set`."""
    fixed = FixedClock(NOW)
    # Структурная проверка mypy: FixedClock должен удовлетворять протоколу Clock.
    conforms: Clock = fixed
    assert conforms is fixed
    return fixed


@pytest.fixture
def uow_factory() -> FakeUnitOfWorkFactory:
    """Фабрика in-memory `UnitOfWork` с общим на все транзакции `Store`."""
    factory = FakeUnitOfWorkFactory()
    # Структурная проверка mypy: FakeUnitOfWorkFactory должен удовлетворять
    # протоколу UnitOfWorkFactory.
    conforms: UnitOfWorkFactory = factory
    assert conforms is factory
    return factory


@pytest.fixture
def seed(
    uow_factory: FakeUnitOfWorkFactory,
) -> Callable[..., None]:
    """Кладёт объекты сразу в закоммиченное хранилище фабрики, минуя UoW.

    Используется для подготовки данных теста до вызова use case — сам use
    case видит эти данные как уже сохранённые предыдущей транзакцией.
    """

    def _seed(
        *,
        users: Iterable[User] = (),
        accounts: Iterable[Account] = (),
        categories: Iterable[Category] = (),
        transactions: Iterable[Transaction] = (),
    ) -> None:
        for user in users:
            uow_factory.store.users[user.id] = user
        for account in accounts:
            uow_factory.store.accounts[account.id] = account
        for category in categories:
            uow_factory.store.categories[category.id] = category
        for transaction in transactions:
            uow_factory.store.transactions[transaction.id] = transaction

    return _seed


@pytest.fixture
def make_user() -> Callable[..., User]:
    """Строит валидного `User`, переопределяя нужные поля."""

    def _make(
        *,
        telegram_id: int | None = None,
        username: str | None = "user",
        first_name: str = "Имя",
        base_currency: Currency = RUB,
        timezone: str = "Europe/Moscow",
        created_at: datetime = NOW,
    ) -> User:
        return User(
            id=uuid4(),
            telegram_id=telegram_id if telegram_id is not None else next(_telegram_id_counter),
            username=username,
            first_name=first_name,
            created_at=created_at,
            base_currency=base_currency,
            timezone=timezone,
        )

    return _make


@pytest.fixture
def make_account() -> Callable[..., Account]:
    """Строит валидный `Account`, переопределяя нужные поля."""

    def _make(
        *,
        user_id: UUID,
        name: str = "Счёт",
        account_type: AccountType = AccountType.CASH,
        currency: Currency = RUB,
        opening_balance: Decimal = Decimal("0"),
        opened_at: date = date(2026, 1, 1),
        is_archived: bool = False,
        include_in_networth: bool = True,
    ) -> Account:
        return Account(
            id=uuid4(),
            user_id=user_id,
            name=name,
            type=account_type,
            currency=currency,
            opening_balance=Money(opening_balance, currency),
            opened_at=opened_at,
            is_archived=is_archived,
            include_in_networth=include_in_networth,
        )

    return _make


@pytest.fixture
def make_category() -> Callable[..., Category]:
    """Строит валидную `Category` — корень или потомок переданного `parent`."""

    def _make(
        *,
        user_id: UUID,
        kind: CategoryKind = CategoryKind.EXPENSE,
        slug: str = "misc",
        name: str = "Прочее",
        is_archived: bool = False,
        parent: Category | None = None,
    ) -> Category:
        if parent is None:
            return Category.new_root(
                id=uuid4(),
                user_id=user_id,
                kind=kind,
                slug=slug,
                name=name,
                is_archived=is_archived,
            )
        return Category.new_child(
            id=uuid4(),
            parent=parent,
            slug=slug,
            name=name,
            is_archived=is_archived,
        )

    return _make


@pytest.fixture
def make_transaction() -> Callable[..., Transaction]:
    """Строит валидную `Transaction` через `Transaction.new`.

    `now` для проверки «не более чем на сутки в будущем» (раздел 3.3) по
    умолчанию берётся равным `occurred_at`, чтобы граничные даты в тестах
    периодов не спотыкались об это ограничение.
    """

    def _make(
        *,
        user_id: UUID,
        account_id: UUID,
        kind: TransactionKind = TransactionKind.EXPENSE,
        category_id: UUID | None = None,
        amount: Decimal = Decimal("100.00"),
        currency: Currency = RUB,
        occurred_at: datetime = NOW,
        status: TransactionStatus = TransactionStatus.POSTED,
        source: str = "bot",
        reverses_id: UUID | None = None,
        created_at: datetime | None = None,
        external_key: str | None = None,
    ) -> Transaction:
        return Transaction.new(
            id=uuid4(),
            user_id=user_id,
            kind=kind,
            status=status,
            amount=Money(amount, currency),
            account_id=account_id,
            occurred_at=occurred_at,
            base_amount=amount,
            base_currency=currency,
            base_rate=Decimal("1"),
            source=source,
            created_at=created_at or occurred_at,
            now=occurred_at,
            category_id=category_id,
            reverses_id=reverses_id,
            external_key=external_key,
        )

    return _make
