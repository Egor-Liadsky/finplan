"""Порты репозиториев и чтения журнала для use case этапа 1.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции», раздел 4.2 «Неизменяемый журнал против пересчитываемых данных»
и раздел 8.5, пункт 2: ни один метод репозитория не принимает идентификатор
объекта без `user_id`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind
from finplan.domain.entities.user import User


class DuplicateError(Exception):
    """Нарушение уникального ключа в реализации репозитория.

    Бросается при повторе `external_key` операции, имени счёта или `path`
    категории в пределах одного пользователя (раздел 2.2).
    """


class UserRepository(Protocol):
    """Доступ к пользователям."""

    async def get(self, user_id: UUID) -> User | None:
        """Возвращает пользователя по `id` или `None`, если его нет."""
        ...

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Возвращает пользователя по `telegram_id` или `None`, если его нет."""
        ...

    async def add(self, user: User) -> None:
        """Сохраняет нового пользователя."""
        ...


class AccountRepository(Protocol):
    """Доступ к счетам и активам пользователя."""

    async def get(self, user_id: UUID, account_id: UUID) -> Account | None:
        """Возвращает счёт пользователя по `id` или `None`, если его нет."""
        ...

    async def list(self, user_id: UUID, *, include_archived: bool = False) -> Sequence[Account]:
        """Возвращает счета пользователя; архивные — только если `include_archived`."""
        ...

    async def add(self, account: Account) -> None:
        """Сохраняет новый счёт."""
        ...


class CategoryRepository(Protocol):
    """Доступ к категориям пользователя."""

    async def get(self, user_id: UUID, category_id: UUID) -> Category | None:
        """Возвращает категорию пользователя по `id` или `None`, если её нет."""
        ...

    async def list(
        self, user_id: UUID, kind: CategoryKind, *, include_archived: bool = False
    ) -> Sequence[Category]:
        """Возвращает категории пользователя заданного вида; архивные — по флагу."""
        ...

    async def add_many(self, categories: Sequence[Category]) -> None:
        """Сохраняет несколько категорий разом, например дефолтный набор."""
        ...


class TransactionRepository(Protocol):
    """Доступ к журналу операций пользователя."""

    async def get(self, user_id: UUID, transaction_id: UUID) -> Transaction | None:
        """Возвращает операцию пользователя по `id` или `None`, если её нет."""
        ...

    async def add(self, transaction: Transaction) -> None:
        """Сохраняет новую операцию."""
        ...

    async def mark_reversed(self, user_id: UUID, transaction_id: UUID) -> None:
        """Переводит операцию из `posted` в `reversed`.

        Единственное изменение строки журнала, которое допускает раздел 4.2.
        """
        ...

    async def last_reversible(self, user_id: UUID, source: str) -> Transaction | None:
        """Возвращает последнюю по `created_at` операцию `source` в статусе
        `posted` без `reverses_id`, либо `None`, если сторнировать нечего.
        """
        ...


@dataclass(frozen=True, slots=True)
class CategoryTotal:
    """Сумма операций одной категории за период."""

    category_id: UUID
    kind: TransactionKind
    base_amount: Decimal


class LedgerQueries(Protocol):
    """Чтение агрегатов журнала: остатков и сумм за период.

    Учитывает только операции в статусе `posted`: пара «исходная запись и
    сторно» в агрегаты не попадает (раздел 2.2).
    """

    async def account_movements(self, user_id: UUID) -> Mapping[UUID, Decimal]:
        """Сумма движений по каждому счёту в валюте счёта, без `opening_balance`.

        Доход и начисленные проценты (`interest`) — со знаком плюс, расход —
        со знаком минус, перевод — минус по
        `account_id` и плюс по `counter_account_id`. Счёт без операций в
        словарь не попадает.
        """
        ...

    async def totals_by_category(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> Sequence[CategoryTotal]:
        """Суммы `base_amount` операций `expense` и `income` по категориям
        за полуинтервал `[start, end)` по `occurred_at`.
        """
        ...
