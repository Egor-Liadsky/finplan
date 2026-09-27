"""Модульные тесты `RecordTransaction`.

`docs/architecture.md`, раздел 3.3, таблица `Transaction` и раздел 3.1,
абзац «Арифметика»: сумма операции всегда положительна, знак движения
задаёт `TransactionKind`, а не знак суммы.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fakes import FakeUnitOfWorkFactory, FixedClock

from finplan.application.dto.transactions import RecordTransactionCommand
from finplan.application.errors import InvalidCommandError, NotFoundError
from finplan.application.use_cases.transactions.record_transaction import RecordTransaction
from finplan.domain.common.currency import RUB, USD
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import TransactionKind
from finplan.domain.entities.user import User


@pytest.mark.parametrize(
    ("kind", "category_kind"),
    [
        (TransactionKind.EXPENSE, CategoryKind.EXPENSE),
        (TransactionKind.INCOME, CategoryKind.INCOME),
    ],
)
async def test_expense_and_income_are_saved_with_positive_amount_and_matching_kind(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    kind: TransactionKind,
    category_kind: CategoryKind,
) -> None:
    user = make_user()
    account = make_account(user_id=user.id, currency=RUB)
    category = make_category(user_id=user.id, kind=category_kind)
    seed(users=[user], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    result = await use_case(
        RecordTransactionCommand(
            user_id=user.id,
            kind=kind,
            amount=Decimal("250.50"),
            account_id=account.id,
            category_id=category.id,
            occurred_at=None,
            comment=None,
            external_key=None,
            source="bot",
        )
    )

    assert result.kind is kind
    assert result.amount == Decimal("250.50")
    assert result.category_id == category.id
    assert result.occurred_at == clock.now()
    assert uow_factory.transactions[-1].committed is True


async def test_occurred_on_is_computed_in_user_timezone(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    user = make_user(timezone="Europe/Moscow")
    account = make_account(user_id=user.id, currency=RUB)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    seed(users=[user], accounts=[account], categories=[category])
    clock.set(datetime(2026, 9, 23, 22, 30, tzinfo=UTC))

    use_case = RecordTransaction(uow_factory, clock)
    result = await use_case(
        RecordTransactionCommand(
            user_id=user.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("10.00"),
            account_id=account.id,
            category_id=category.id,
            occurred_at=datetime(2026, 9, 23, 22, 30, tzinfo=UTC),
            comment=None,
            external_key=None,
            source="bot",
        )
    )

    assert result.occurred_on == date(2026, 9, 24)


async def test_occurred_on_is_computed_in_user_timezone_with_negative_offset(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    """Раздел 3.3: у пользователя с отрицательным смещением от UTC
    (`America/Los_Angeles`, UTC-7 в сентябре) операция, для которой в UTC
    уже наступил `2026-09-24`, получает `occurred_on = 2026-09-23` — дату,
    которая всё ещё текущая по местному времени пользователя.
    """
    user = make_user(timezone="America/Los_Angeles")
    account = make_account(user_id=user.id, currency=RUB)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    seed(users=[user], accounts=[account], categories=[category])
    clock.set(datetime(2026, 9, 24, 2, 30, tzinfo=UTC))

    use_case = RecordTransaction(uow_factory, clock)
    result = await use_case(
        RecordTransactionCommand(
            user_id=user.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("10.00"),
            account_id=account.id,
            category_id=category.id,
            occurred_at=datetime(2026, 9, 24, 2, 30, tzinfo=UTC),
            comment=None,
            external_key=None,
            source="bot",
        )
    )

    assert result.occurred_on == date(2026, 9, 23)


async def test_missing_account_raises_not_found(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_category: Callable[..., Category],
) -> None:
    user = make_user()
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    seed(users=[user], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(NotFoundError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("10.00"),
                account_id=uuid4(),
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )

    assert uow_factory.store.transactions == {}
    assert uow_factory.transactions[-1].committed is False


async def test_foreign_account_raises_not_found(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    owner = make_user()
    stranger = make_user()
    account = make_account(user_id=owner.id, currency=RUB)
    category = make_category(user_id=stranger.id, kind=CategoryKind.EXPENSE)
    seed(users=[owner, stranger], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(NotFoundError):
        await use_case(
            RecordTransactionCommand(
                user_id=stranger.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )


async def test_archived_account_raises_not_found(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    user = make_user()
    account = make_account(user_id=user.id, currency=RUB, is_archived=True)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    seed(users=[user], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(NotFoundError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )


async def test_missing_category_raises_not_found(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
) -> None:
    user = make_user()
    account = make_account(user_id=user.id, currency=RUB)
    seed(users=[user], accounts=[account])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(NotFoundError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=uuid4(),
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )


async def test_foreign_category_raises_not_found(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    owner = make_user()
    stranger = make_user()
    account = make_account(user_id=stranger.id, currency=RUB)
    category = make_category(user_id=owner.id, kind=CategoryKind.EXPENSE)
    seed(users=[owner, stranger], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(NotFoundError):
        await use_case(
            RecordTransactionCommand(
                user_id=stranger.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )


async def test_archived_category_raises_not_found(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    user = make_user()
    account = make_account(user_id=user.id, currency=RUB)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, is_archived=True)
    seed(users=[user], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(NotFoundError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )


async def test_account_currency_different_from_base_currency_raises_invalid_command(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    user = make_user(base_currency=RUB)
    account = make_account(user_id=user.id, currency=USD)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    seed(users=[user], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(InvalidCommandError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )


@pytest.mark.parametrize(
    ("kind", "category_kind"),
    [
        (TransactionKind.EXPENSE, CategoryKind.INCOME),
        (TransactionKind.INCOME, CategoryKind.EXPENSE),
    ],
)
async def test_category_of_wrong_kind_raises_invalid_command(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    kind: TransactionKind,
    category_kind: CategoryKind,
) -> None:
    user = make_user()
    account = make_account(user_id=user.id, currency=RUB)
    category = make_category(user_id=user.id, kind=category_kind)
    seed(users=[user], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(InvalidCommandError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=kind,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )

    assert uow_factory.store.transactions == {}
    assert uow_factory.transactions[-1].committed is False


@pytest.mark.parametrize(
    ("raw_amount", "expected_amount"),
    [
        (Decimal("10.005"), Decimal("10.01")),
        (Decimal("10.004"), Decimal("10.00")),
    ],
)
async def test_amount_is_rounded_half_up_to_minor_unit_and_matches_base_amount(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    raw_amount: Decimal,
    expected_amount: Decimal,
) -> None:
    # Раздел 3.1: валюты с minor_unit = 0 (например, JPY) в заглушках
    # тестов не заведены (`fakes.py`/`conftest.py` знают только RUB, USD,
    # EUR — у всех minor_unit = 2), поэтому этот случай проверяется только
    # на RUB.
    user = make_user(base_currency=RUB)
    account = make_account(user_id=user.id, currency=RUB)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    seed(users=[user], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    result = await use_case(
        RecordTransactionCommand(
            user_id=user.id,
            kind=TransactionKind.EXPENSE,
            amount=raw_amount,
            account_id=account.id,
            category_id=category.id,
            occurred_at=None,
            comment=None,
            external_key=None,
            source="bot",
        )
    )

    assert result.amount == expected_amount
    stored = uow_factory.store.transactions[result.id]
    assert stored.amount.amount == expected_amount
    assert stored.base_amount == expected_amount


async def test_amount_rounding_to_zero_raises_invalid_command(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    user = make_user(base_currency=RUB)
    account = make_account(user_id=user.id, currency=RUB)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    seed(users=[user], accounts=[account], categories=[category])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(InvalidCommandError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount=Decimal("0.004"),
                account_id=account.id,
                category_id=category.id,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )

    assert uow_factory.store.transactions == {}
    assert uow_factory.transactions[-1].committed is False


async def test_transfer_kind_raises_invalid_command(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
) -> None:
    user = make_user()
    account = make_account(user_id=user.id, currency=RUB)
    seed(users=[user], accounts=[account])

    use_case = RecordTransaction(uow_factory, clock)
    with pytest.raises(InvalidCommandError):
        await use_case(
            RecordTransactionCommand(
                user_id=user.id,
                kind=TransactionKind.TRANSFER,
                amount=Decimal("10.00"),
                account_id=account.id,
                category_id=None,
                occurred_at=None,
                comment=None,
                external_key=None,
                source="bot",
            )
        )

    assert uow_factory.store.transactions == {}
