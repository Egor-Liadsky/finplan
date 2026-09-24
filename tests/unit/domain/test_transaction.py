"""Модульные тесты `Transaction`.

`docs/architecture.md`, раздел 3.3 (таблица `Transaction` и «Инварианты»,
включая «Форма сторно») и раздел 4.2 (неизменяемый журнал). Каждый инвариант
закрыт положительным и отрицательным случаем: положительный знак суммы,
соответствие `category_id`/`counter_account_id` виду операции, сторно.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, tzinfo
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from finplan.domain.common.currency import RUB
from finplan.domain.common.errors import AlreadyReversedError, InvariantViolationError
from finplan.domain.common.money import Money
from finplan.domain.entities.transaction import (
    Transaction,
    TransactionKind,
    TransactionStatus,
)

_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

#: Сентинел «параметр не переопределён» — отличим от осмысленного `None`.
_UNSET = object()


def _make_transaction(
    *,
    kind: TransactionKind = TransactionKind.EXPENSE,
    status: TransactionStatus = TransactionStatus.POSTED,
    amount: Decimal = Decimal("100.00"),
    account_id: UUID | None = None,
    counter_account_id: UUID | None = None,
    category_id: object = _UNSET,
    occurred_at: datetime | None = None,
    occurred_on: date | None = None,
    reverses_id: UUID | None = None,
    external_key: str | None = None,
) -> Transaction:
    """Строит валидную по умолчанию `Transaction`, переопределяя нужные поля.

    `category_id` по умолчанию выставляется автоматически: `uuid4()` для
    `income`/`expense`, `None` для остальных видов — так каждый тест меняет
    только то поле, которое действительно проверяет. `occurred_on` по
    умолчанию — дата `occurred_at` в UTC, как для `Transaction.new` с
    `timezone = UTC`.
    """
    resolved_category_id = (
        (uuid4() if kind in (TransactionKind.INCOME, TransactionKind.EXPENSE) else None)
        if category_id is _UNSET
        else category_id
    )
    resolved_occurred_at = occurred_at or _NOW
    return Transaction(
        id=uuid4(),
        user_id=uuid4(),
        kind=kind,
        status=status,
        amount=Money(amount, RUB),
        account_id=account_id or uuid4(),
        counter_account_id=counter_account_id,
        category_id=resolved_category_id,
        occurred_at=resolved_occurred_at,
        occurred_on=occurred_on or resolved_occurred_at.date(),
        comment=None,
        base_amount=amount,
        base_currency=RUB,
        base_rate=Decimal("1"),
        external_key=external_key,
        source="bot",
        recurring_rule_id=None,
        deposit_id=None,
        goal_id=None,
        reverses_id=reverses_id,
        created_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Положительный знак суммы
# ---------------------------------------------------------------------------


def test_positive_amount_is_accepted() -> None:
    transaction = _make_transaction(amount=Decimal("100.00"))
    assert transaction.amount.amount == Decimal("100.00")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-0.01"), Decimal("-100")])
def test_non_positive_amount_is_rejected(amount: Decimal) -> None:
    with pytest.raises(InvariantViolationError):
        _make_transaction(amount=amount)


# ---------------------------------------------------------------------------
# Соответствие вида операции и категории/счёта-получателя
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [TransactionKind.INCOME, TransactionKind.EXPENSE])
def test_income_and_expense_require_category(kind: TransactionKind) -> None:
    with pytest.raises(InvariantViolationError):
        _make_transaction(kind=kind, category_id=None)


@pytest.mark.parametrize("kind", [TransactionKind.INCOME, TransactionKind.EXPENSE])
def test_income_and_expense_with_category_are_accepted(kind: TransactionKind) -> None:
    transaction = _make_transaction(kind=kind, category_id=uuid4())
    assert transaction.category_id is not None


def test_transfer_forbids_category() -> None:
    with pytest.raises(InvariantViolationError):
        _make_transaction(
            kind=TransactionKind.TRANSFER,
            counter_account_id=uuid4(),
            category_id=uuid4(),
        )


def test_transfer_without_category_is_accepted() -> None:
    transaction = _make_transaction(kind=TransactionKind.TRANSFER, counter_account_id=uuid4())
    assert transaction.category_id is None
    assert transaction.counter_account_id is not None


def test_transfer_requires_counter_account() -> None:
    with pytest.raises(InvariantViolationError):
        _make_transaction(kind=TransactionKind.TRANSFER, counter_account_id=None)


def test_transfer_counter_account_must_differ_from_account() -> None:
    account_id = uuid4()
    with pytest.raises(InvariantViolationError):
        _make_transaction(
            kind=TransactionKind.TRANSFER,
            account_id=account_id,
            counter_account_id=account_id,
        )


def test_counter_account_forbidden_outside_transfer() -> None:
    with pytest.raises(InvariantViolationError):
        _make_transaction(
            kind=TransactionKind.INCOME,
            category_id=uuid4(),
            counter_account_id=uuid4(),
        )


@pytest.mark.parametrize("kind", [TransactionKind.ADJUSTMENT, TransactionKind.INTEREST])
def test_adjustment_and_interest_do_not_require_category(kind: TransactionKind) -> None:
    """`adjustment` и `interest` не входят в виды, требующие категорию
    (раздел 3.2: `adjustment` — ручная корректировка; проценты по вкладам
    категорию не требуют, раздел 3.3, «Дефолтный набор»)."""
    transaction = _make_transaction(kind=kind, category_id=None)
    assert transaction.category_id is None


# ---------------------------------------------------------------------------
# Ограничение на будущий `occurred_at` (только через `Transaction.new`)
# ---------------------------------------------------------------------------


def _new_transaction(
    *,
    status: TransactionStatus,
    occurred_at: datetime,
    now: datetime = _NOW,
    timezone: tzinfo = UTC,
) -> Transaction:
    return Transaction.new(
        id=uuid4(),
        user_id=uuid4(),
        kind=TransactionKind.EXPENSE,
        status=status,
        amount=Money(Decimal("10.00"), RUB),
        account_id=uuid4(),
        occurred_at=occurred_at,
        timezone=timezone,
        base_amount=Decimal("10.00"),
        base_currency=RUB,
        base_rate=Decimal("1"),
        source="bot",
        created_at=now,
        now=now,
        category_id=uuid4(),
    )


def test_posted_transaction_more_than_one_day_in_future_is_rejected() -> None:
    with pytest.raises(InvariantViolationError):
        _new_transaction(status=TransactionStatus.POSTED, occurred_at=_NOW + timedelta(days=2))


def test_posted_transaction_within_one_day_in_future_is_accepted() -> None:
    transaction = _new_transaction(
        status=TransactionStatus.POSTED, occurred_at=_NOW + timedelta(hours=12)
    )
    assert transaction.status is TransactionStatus.POSTED


def test_pending_transaction_far_in_future_is_accepted() -> None:
    """Раздел 3.2: `pending` — запланированная, ещё не проведённая операция;
    ограничение на будущее относится только к `status = posted`."""
    transaction = _new_transaction(
        status=TransactionStatus.PENDING, occurred_at=_NOW + timedelta(days=30)
    )
    assert transaction.status is TransactionStatus.PENDING


# ---------------------------------------------------------------------------
# `occurred_on` — календарная дата `occurred_at` в таймзоне пользователя
# ---------------------------------------------------------------------------


def test_occurred_on_uses_user_timezone_moscow() -> None:
    transaction = _new_transaction(
        status=TransactionStatus.POSTED,
        occurred_at=datetime(2026, 9, 23, 22, 30, tzinfo=UTC),
        now=datetime(2026, 9, 23, 23, 0, tzinfo=UTC),
        timezone=ZoneInfo("Europe/Moscow"),
    )
    assert transaction.occurred_on == date(2026, 9, 24)


def test_occurred_on_uses_utc_when_timezone_is_utc() -> None:
    transaction = _new_transaction(
        status=TransactionStatus.POSTED,
        occurred_at=datetime(2026, 9, 23, 22, 30, tzinfo=UTC),
        now=datetime(2026, 9, 23, 23, 0, tzinfo=UTC),
        timezone=UTC,
    )
    assert transaction.occurred_on == date(2026, 9, 23)


def test_naive_occurred_at_is_rejected() -> None:
    with pytest.raises(InvariantViolationError):
        _new_transaction(
            status=TransactionStatus.POSTED,
            occurred_at=datetime(2026, 9, 23, 22, 30),  # naive — как раз проверяем это отклонение
            timezone=UTC,
        )


# ---------------------------------------------------------------------------
# Сторно
# ---------------------------------------------------------------------------


def test_reverse_moves_original_from_posted_to_reversed() -> None:
    original = _make_transaction(status=TransactionStatus.POSTED)
    reversed_original, _reversal = original.reverse(
        reversal_id=uuid4(), created_at=_NOW + timedelta(minutes=1)
    )
    assert reversed_original.status is TransactionStatus.REVERSED
    assert reversed_original.id == original.id


def test_reversal_copies_original_and_is_created_as_reversed() -> None:
    original = _make_transaction(
        status=TransactionStatus.POSTED,
        external_key="idem-1",
        amount=Decimal("42.00"),
        occurred_at=datetime(2026, 9, 23, 22, 30, tzinfo=UTC),
        occurred_on=date(2026, 9, 24),
    )
    reversal_id = uuid4()
    created_at = _NOW + timedelta(minutes=1)
    _reversed_original, reversal = original.reverse(reversal_id=reversal_id, created_at=created_at)

    assert reversal.id == reversal_id
    assert reversal.status is TransactionStatus.REVERSED
    assert reversal.reverses_id == original.id
    assert reversal.created_at == created_at
    # Копия исходных полей движения денег (раздел 3.3, «Форма сторно»).
    assert reversal.kind == original.kind
    assert reversal.amount == original.amount
    assert reversal.account_id == original.account_id
    assert reversal.counter_account_id == original.counter_account_id
    assert reversal.category_id == original.category_id
    assert reversal.occurred_at == original.occurred_at
    assert reversal.occurred_on == original.occurred_on
    assert reversal.occurred_on == date(2026, 9, 24)
    assert reversal.base_amount == original.base_amount
    assert reversal.base_currency == original.base_currency
    assert reversal.base_rate == original.base_rate
    # `external_key` сторнирующей записи не копируется (уникален в паре с user_id).
    assert reversal.external_key is None


def test_reversing_already_reversed_transaction_raises_already_reversed_error() -> None:
    original = _make_transaction(status=TransactionStatus.POSTED)
    reversed_original, _reversal = original.reverse(
        reversal_id=uuid4(), created_at=_NOW + timedelta(minutes=1)
    )
    with pytest.raises(AlreadyReversedError):
        reversed_original.reverse(reversal_id=uuid4(), created_at=_NOW + timedelta(minutes=2))


@pytest.mark.parametrize("status", [TransactionStatus.PENDING, TransactionStatus.REVERSED])
def test_reversing_non_posted_transaction_raises_already_reversed_error(
    status: TransactionStatus,
) -> None:
    transaction = _make_transaction(status=status)
    with pytest.raises(AlreadyReversedError):
        transaction.reverse(reversal_id=uuid4(), created_at=_NOW + timedelta(minutes=1))
