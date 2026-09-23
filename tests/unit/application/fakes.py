"""In-memory реализации портов `application/ports/` для модульных тестов use case.

`docs/architecture.md`, раздел 11.1 «Модульные с заглушками»: `application/use_cases`
покрываются тестами с in-memory реализациями портов, реальный IO не поднимается.
Раздел 2.2, абзац «Контракт портов и граница транзакции», задаёт семантику,
которую здесь нужно воспроизвести: транзакция открывается и коммитится явно,
выход из блока без `commit` откатывает изменения, а `DuplicateError` бросает
реализация репозитория при нарушении уникального ключа.

Каждая Fake-реализация присваивается переменной, аннотированной типом
протокола из `ports/` (см. `FakeUnitOfWork.__aenter__` и
`FakeUnitOfWorkFactory.__call__`) — так `mypy` подтверждает структурное
соответствие протоколу в месте, где объект реально создаётся, а не в
отдельной неисполняемой проверке.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from types import TracebackType
from typing import Self
from uuid import UUID

from finplan.application.ports.repositories import (
    AccountRepository,
    CategoryRepository,
    CategoryTotal,
    DuplicateError,
    LedgerQueries,
    TransactionRepository,
    UserRepository,
)
from finplan.application.ports.uow import UnitOfWork
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind, TransactionStatus
from finplan.domain.entities.user import User


@dataclass
class _Staged:
    """Рабочая копия хранилища одной открытой транзакции (снимок `Store`)."""

    users: dict[UUID, User]
    accounts: dict[UUID, Account]
    categories: dict[UUID, Category]
    transactions: dict[UUID, Transaction]


@dataclass
class Store:
    """Общее для одной фабрики хранилище: то, что уже закоммичено.

    `pending_races` — тестовый крючок для гонки регистрации (раздел 2.2):
    ключ — `telegram_id`, значение — пара «пользователь, счёт», которые
    как будто успела закоммитить параллельная транзакция ровно в момент,
    когда текущая транзакция вызывает `UserRepository.add` с тем же
    `telegram_id`. До этого момента хранилище пользователя не содержит —
    так `get_by_telegram_id`, вызванный раньше, законно возвращает `None`.
    """

    users: dict[UUID, User] = field(default_factory=dict)
    accounts: dict[UUID, Account] = field(default_factory=dict)
    categories: dict[UUID, Category] = field(default_factory=dict)
    transactions: dict[UUID, Transaction] = field(default_factory=dict)
    pending_races: dict[int, tuple[User, Account]] = field(default_factory=dict)

    def snapshot(self) -> _Staged:
        """Копия текущего закоммиченного состояния для новой транзакции."""
        return _Staged(
            users=dict(self.users),
            accounts=dict(self.accounts),
            categories=dict(self.categories),
            transactions=dict(self.transactions),
        )

    def apply(self, staged: _Staged) -> None:
        """Переносит рабочую копию транзакции в закоммиченное состояние."""
        self.users = dict(staged.users)
        self.accounts = dict(staged.accounts)
        self.categories = dict(staged.categories)
        self.transactions = dict(staged.transactions)


@dataclass
class TransactionRecord:
    """История одной открытой фабрикой транзакции для проверок в тестах."""

    user_id: UUID | None
    committed: bool = False


class FakeUserRepository:
    """`UserRepository` поверх рабочей копии транзакции."""

    def __init__(self, staged: _Staged, store: Store) -> None:
        self._staged = staged
        self._store = store

    async def get(self, user_id: UUID) -> User | None:
        return self._staged.users.get(user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        for user in self._staged.users.values():
            if user.telegram_id == telegram_id:
                return user
        return None

    async def add(self, user: User) -> None:
        race = self._store.pending_races.pop(user.telegram_id, None)
        if race is not None:
            existing_user, existing_account = race
            self._store.users = {**self._store.users, existing_user.id: existing_user}
            self._store.accounts = {**self._store.accounts, existing_account.id: existing_account}
            raise DuplicateError(f"telegram_id={user.telegram_id} уже занят")
        already_used = any(
            existing.telegram_id == user.telegram_id for existing in self._staged.users.values()
        )
        if already_used:
            raise DuplicateError(f"telegram_id={user.telegram_id} уже занят")
        self._staged.users[user.id] = user


class FakeAccountRepository:
    """`AccountRepository` поверх рабочей копии транзакции."""

    def __init__(self, staged: _Staged) -> None:
        self._staged = staged

    async def get(self, user_id: UUID, account_id: UUID) -> Account | None:
        account = self._staged.accounts.get(account_id)
        if account is None or account.user_id != user_id:
            return None
        return account

    async def list(self, user_id: UUID, *, include_archived: bool = False) -> Sequence[Account]:
        return [
            account
            for account in self._staged.accounts.values()
            if account.user_id == user_id and (include_archived or not account.is_archived)
        ]

    async def add(self, account: Account) -> None:
        self._staged.accounts[account.id] = account


class FakeCategoryRepository:
    """`CategoryRepository` поверх рабочей копии транзакции."""

    def __init__(self, staged: _Staged) -> None:
        self._staged = staged

    async def get(self, user_id: UUID, category_id: UUID) -> Category | None:
        category = self._staged.categories.get(category_id)
        if category is None or category.user_id != user_id:
            return None
        return category

    async def list(
        self, user_id: UUID, kind: CategoryKind, *, include_archived: bool = False
    ) -> Sequence[Category]:
        return [
            category
            for category in self._staged.categories.values()
            if category.user_id == user_id
            and category.kind == kind
            and (include_archived or not category.is_archived)
        ]

    async def add_many(self, categories: Sequence[Category]) -> None:
        for category in categories:
            self._staged.categories[category.id] = category


class FakeTransactionRepository:
    """`TransactionRepository` поверх рабочей копии транзакции."""

    def __init__(self, staged: _Staged) -> None:
        self._staged = staged

    async def get(self, user_id: UUID, transaction_id: UUID) -> Transaction | None:
        transaction = self._staged.transactions.get(transaction_id)
        if transaction is None or transaction.user_id != user_id:
            return None
        return transaction

    async def add(self, transaction: Transaction) -> None:
        self._staged.transactions[transaction.id] = transaction

    async def mark_reversed(self, user_id: UUID, transaction_id: UUID) -> None:
        transaction = self._staged.transactions.get(transaction_id)
        if transaction is None or transaction.user_id != user_id:
            raise LookupError(f"операция {transaction_id} не найдена у пользователя {user_id}")
        self._staged.transactions[transaction_id] = _with_status(
            transaction, TransactionStatus.REVERSED
        )

    async def last_reversible(self, user_id: UUID, source: str) -> Transaction | None:
        candidates = [
            transaction
            for transaction in self._staged.transactions.values()
            if transaction.user_id == user_id
            and transaction.source == source
            and transaction.status is TransactionStatus.POSTED
            and transaction.reverses_id is None
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda transaction: transaction.created_at)


def _with_status(transaction: Transaction, status: TransactionStatus) -> Transaction:
    """Возвращает копию `transaction` с изменённым `status`.

    Единственное поле, которое реализации репозитория позволено менять у
    проведённой операции (раздел 4.2), — `Transaction` при этом не даёт
    менять себя иначе, чем через `dataclasses.replace`.
    """
    return replace(transaction, status=status)


class FakeLedgerQueries:
    """`LedgerQueries` поверх рабочей копии транзакции.

    Учитывает только `status = posted` (раздел 2.2): пара «исходная запись и
    сторно» получает `status = reversed` на обеих сторонах и потому в
    агрегаты не попадает.
    """

    def __init__(self, staged: _Staged) -> None:
        self._staged = staged

    async def account_movements(self, user_id: UUID) -> Mapping[UUID, Decimal]:
        movements: dict[UUID, Decimal] = {}

        def _add(account_id: UUID, amount: Decimal) -> None:
            movements[account_id] = movements.get(account_id, Decimal(0)) + amount

        for transaction in self._staged.transactions.values():
            if transaction.user_id != user_id or transaction.status is not TransactionStatus.POSTED:
                continue
            amount = transaction.amount.amount
            if transaction.kind is TransactionKind.INCOME:
                _add(transaction.account_id, amount)
            elif transaction.kind is TransactionKind.EXPENSE:
                _add(transaction.account_id, -amount)
            elif transaction.kind is TransactionKind.TRANSFER:
                _add(transaction.account_id, -amount)
                if transaction.counter_account_id is not None:
                    _add(transaction.counter_account_id, amount)
            elif transaction.kind is TransactionKind.INTEREST:
                _add(transaction.account_id, amount)
        return movements

    async def totals_by_category(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> Sequence[CategoryTotal]:
        totals: dict[UUID, Decimal] = {}
        kind_by_category: dict[UUID, TransactionKind] = {}
        for transaction in self._staged.transactions.values():
            if transaction.user_id != user_id or transaction.status is not TransactionStatus.POSTED:
                continue
            if transaction.kind not in (TransactionKind.EXPENSE, TransactionKind.INCOME):
                continue
            if transaction.category_id is None:
                continue
            if not (start <= transaction.occurred_at < end):
                continue
            category_id = transaction.category_id
            totals[category_id] = totals.get(category_id, Decimal(0)) + transaction.base_amount
            kind_by_category[category_id] = transaction.kind
        return [
            CategoryTotal(
                category_id=category_id,
                kind=kind_by_category[category_id],
                base_amount=amount,
            )
            for category_id, amount in totals.items()
        ]


class FakeUnitOfWork:
    """`UnitOfWork` in-memory: коммитит рабочую копию в `Store` только по `commit`."""

    def __init__(self, store: Store, record: TransactionRecord) -> None:
        self._store = store
        self._record = record
        self._staged: _Staged | None = None
        self.users: UserRepository
        self.accounts: AccountRepository
        self.categories: CategoryRepository
        self.transactions: TransactionRepository
        self.ledger: LedgerQueries

    async def __aenter__(self) -> Self:
        staged = self._store.snapshot()
        self._staged = staged
        users: UserRepository = FakeUserRepository(staged, self._store)
        accounts: AccountRepository = FakeAccountRepository(staged)
        categories: CategoryRepository = FakeCategoryRepository(staged)
        transactions: TransactionRepository = FakeTransactionRepository(staged)
        ledger: LedgerQueries = FakeLedgerQueries(staged)
        self.users = users
        self.accounts = accounts
        self.categories = categories
        self.transactions = transactions
        self.ledger = ledger
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Без явного `commit()` рабочая копия просто отбрасывается вместе с
        # выходом из блока — ровно контракт раздела 2.2.
        self._staged = None

    async def commit(self) -> None:
        assert self._staged is not None, "commit() вызван вне открытой транзакции"
        self._store.apply(self._staged)
        self._record.committed = True

    async def rollback(self) -> None:
        assert self._staged is not None, "rollback() вызван вне открытой транзакции"
        fresh = self._store.snapshot()
        self._staged.users.clear()
        self._staged.users.update(fresh.users)
        self._staged.accounts.clear()
        self._staged.accounts.update(fresh.accounts)
        self._staged.categories.clear()
        self._staged.categories.update(fresh.categories)
        self._staged.transactions.clear()
        self._staged.transactions.update(fresh.transactions)


class FakeUnitOfWorkFactory:
    """`UnitOfWorkFactory` in-memory: одно `Store` на все открытые транзакции."""

    def __init__(self) -> None:
        self.store = Store()
        self.transactions: list[TransactionRecord] = []

    def __call__(self, user_id: UUID | None) -> UnitOfWork:
        record = TransactionRecord(user_id=user_id)
        self.transactions.append(record)
        uow: UnitOfWork = FakeUnitOfWork(self.store, record)
        return uow


class FixedClock:
    """`Clock` с фиксированным, задаваемым тестом временем."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = now
