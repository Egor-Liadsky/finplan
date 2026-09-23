"""Сущность `Transaction`: центральная сущность, неизменяемый журнал операций.

`docs/architecture.md`, раздел 3.3, таблица `Transaction` и абзацы
«Инварианты» под ней, включая «Форма сторно»; раздел 3.2 для
`TransactionKind` и `TransactionStatus`; раздел 4.2 про неизменяемый журнал.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from finplan.domain.common.currency import Currency
from finplan.domain.common.errors import AlreadyReversedError, InvariantViolationError
from finplan.domain.common.money import Money

#: Раздел 3.3: комментарий операции — не длиннее 500 символов.
MAX_COMMENT_LENGTH = 500

#: Раздел 3.3: `occurred_at` для `posted` — не более чем на сутки в будущем.
MAX_FUTURE_POSTED_LAG = timedelta(days=1)


class TransactionKind(StrEnum):
    """Вид операции (раздел 3.2). `adjustment` — ручная корректировка остатка."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    INTEREST = "interest"


class TransactionStatus(StrEnum):
    """Статус операции (раздел 3.2). `pending` — запланированная, не проведённая."""

    POSTED = "posted"
    REVERSED = "reversed"
    PENDING = "pending"


_CATEGORY_REQUIRED_KINDS = (TransactionKind.INCOME, TransactionKind.EXPENSE)


@dataclass(frozen=True, slots=True)
class Transaction:
    """Операция журнала. После создания не редактируется (раздел 4.2)."""

    id: UUID
    user_id: UUID
    kind: TransactionKind
    status: TransactionStatus
    amount: Money
    account_id: UUID
    counter_account_id: UUID | None
    category_id: UUID | None
    occurred_at: datetime
    comment: str | None
    base_amount: Decimal
    base_currency: Currency
    base_rate: Decimal
    external_key: str | None
    source: str
    recurring_rule_id: UUID | None
    deposit_id: UUID | None
    goal_id: UUID | None
    reverses_id: UUID | None
    created_at: datetime

    def __post_init__(self) -> None:
        if self.amount.amount <= Decimal(0):
            raise InvariantViolationError(
                f"сумма операции должна быть строго больше нуля: {self.amount.amount}"
            )
        if self.comment is not None and len(self.comment) > MAX_COMMENT_LENGTH:
            raise InvariantViolationError(f"комментарий длиннее {MAX_COMMENT_LENGTH} символов")
        if self.kind is TransactionKind.TRANSFER:
            if self.counter_account_id is None:
                raise InvariantViolationError("перевод обязан указывать counter_account_id")
            if self.counter_account_id == self.account_id:
                raise InvariantViolationError(
                    "counter_account_id перевода не может совпадать с account_id"
                )
            if self.category_id is not None:
                raise InvariantViolationError("перевод не может ссылаться на категорию")
        elif self.counter_account_id is not None:
            raise InvariantViolationError("counter_account_id допустим только для kind = transfer")
        if self.kind in _CATEGORY_REQUIRED_KINDS and self.category_id is None:
            raise InvariantViolationError(
                f"операция kind = {self.kind.value} обязана ссылаться на категорию"
            )

    @classmethod
    def new(
        cls,
        *,
        id: UUID,
        user_id: UUID,
        kind: TransactionKind,
        status: TransactionStatus,
        amount: Money,
        account_id: UUID,
        occurred_at: datetime,
        base_amount: Decimal,
        base_currency: Currency,
        base_rate: Decimal,
        source: str,
        created_at: datetime,
        now: datetime,
        counter_account_id: UUID | None = None,
        category_id: UUID | None = None,
        comment: str | None = None,
        external_key: str | None = None,
        recurring_rule_id: UUID | None = None,
        deposit_id: UUID | None = None,
        goal_id: UUID | None = None,
        reverses_id: UUID | None = None,
    ) -> Transaction:
        """Создаёт новую операцию, проверяя ограничение на будущий `occurred_at`.

        `now` — аргумент, а не вызов часов: у домена их нет, `now` в него
        подставляет `application` через порт `Clock` (раздел 3.3).
        """
        if status is TransactionStatus.POSTED and occurred_at > now + MAX_FUTURE_POSTED_LAG:
            raise InvariantViolationError(
                "occurred_at проведённой операции не может быть более чем на "
                f"{MAX_FUTURE_POSTED_LAG} в будущем относительно {now}"
            )
        return cls(
            id=id,
            user_id=user_id,
            kind=kind,
            status=status,
            amount=amount,
            account_id=account_id,
            counter_account_id=counter_account_id,
            category_id=category_id,
            occurred_at=occurred_at,
            comment=comment,
            base_amount=base_amount,
            base_currency=base_currency,
            base_rate=base_rate,
            external_key=external_key,
            source=source,
            recurring_rule_id=recurring_rule_id,
            deposit_id=deposit_id,
            goal_id=goal_id,
            reverses_id=reverses_id,
            created_at=created_at,
        )

    def reverse(
        self, *, reversal_id: UUID, created_at: datetime
    ) -> tuple[Transaction, Transaction]:
        """Сторнирует операцию по правилу «Форма сторно» (раздел 3.3).

        Возвращает пару `(исходная в status=reversed, сторнирующая запись)`.
        Сторнировать можно только операцию в `posted`; повторное сторно и
        сторно сторнирующей записи — доменная ошибка. `external_key`
        сторнирующей записи не копируется: `uq_transactions_user_id_external_key`
        (раздел 4.3) запрещает двум операциям пользователя один и тот же
        ключ идемпотентности, а исходная запись остаётся в таблице со своим.
        """
        if self.status is not TransactionStatus.POSTED:
            raise AlreadyReversedError(
                f"операцию {self.id} в статусе {self.status.value} нельзя сторнировать"
            )
        reversed_original = replace(self, status=TransactionStatus.REVERSED)
        reversal = replace(
            self,
            id=reversal_id,
            status=TransactionStatus.REVERSED,
            external_key=None,
            reverses_id=self.id,
            created_at=created_at,
        )
        return reversed_original, reversal
