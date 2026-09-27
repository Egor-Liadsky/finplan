"""Модульные тесты `UndoLastTransaction`.

`docs/architecture.md`, раздел 3.3, абзац «Форма сторно» — источник истины
для этого файла, а не пересказ в задании: сторнирующая запись **повторяет**
`kind`, `amount`, `account_id`, `category_id`, `occurred_at` и снимок
`base_*` исходной операции, получает `reverses_id` исходной и сразу
`status = reversed`; исходная переходит из `posted` в `reversed`, остальные
её поля не меняются никогда. Обе стороны пары получают `status = reversed`,
поэтому агрегаты, которые считают только `status = posted` (раздел 2.2),
не видят исходную сумму ни разу — не потому, что сторно меняет знак суммы.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

from conftest import NOW
from fakes import FakeUnitOfWorkFactory, FixedClock

from finplan.application.dto.transactions import UndoLastCommand
from finplan.application.use_cases.transactions.undo_last import UndoLastTransaction
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind, TransactionStatus
from finplan.domain.entities.user import User


async def test_undo_creates_new_reversal_and_leaves_original_fields_untouched(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user()
    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    original = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        amount=Decimal("42.00"),
        occurred_at=NOW,
        source="bot",
    )
    seed(users=[user], accounts=[account], categories=[category], transactions=[original])

    use_case = UndoLastTransaction(uow_factory, clock)
    result = await use_case(UndoLastCommand(user_id=user.id, source="bot"))

    assert result is not None
    # Исходная запись — тот же id, тот же набор полей, кроме status.
    assert result.original.id == original.id
    assert result.original.status is TransactionStatus.REVERSED
    assert result.original.amount == original.amount.amount
    assert result.original.account_id == original.account_id
    assert result.original.category_id == original.category_id
    assert result.original.occurred_at == original.occurred_at

    # Сторно — новая запись с другим id, ссылающаяся на исходную.
    assert result.reversal.id != original.id
    assert result.reversal.reverses_id == original.id
    assert result.reversal.status is TransactionStatus.REVERSED
    # «Форма сторно» (раздел 3.3): сумма и остальные поля повторяются, а не
    # инвертируются — направление движения не кодируется знаком (раздел 3.1).
    assert result.reversal.amount == original.amount.amount
    assert result.reversal.kind == original.kind
    assert result.reversal.account_id == original.account_id
    assert result.reversal.category_id == original.category_id
    assert result.reversal.occurred_at == original.occurred_at

    stored_original = uow_factory.store.transactions[original.id]
    assert stored_original.status is TransactionStatus.REVERSED
    assert stored_original.amount == original.amount
    assert stored_original.occurred_at == original.occurred_at
    assert stored_original.comment == original.comment

    assert len(uow_factory.store.transactions) == 2
    assert uow_factory.transactions[-1].committed is True


async def test_second_undo_reverses_previous_transaction_not_the_same_one(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user()
    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    earlier = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        amount=Decimal("10.00"),
        occurred_at=NOW - timedelta(hours=2),
        created_at=NOW - timedelta(hours=2),
        source="bot",
    )
    later = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        amount=Decimal("20.00"),
        occurred_at=NOW - timedelta(hours=1),
        created_at=NOW - timedelta(hours=1),
        source="bot",
    )
    seed(users=[user], accounts=[account], categories=[category], transactions=[earlier, later])

    use_case = UndoLastTransaction(uow_factory, clock)

    first_undo = await use_case(UndoLastCommand(user_id=user.id, source="bot"))
    assert first_undo is not None
    assert first_undo.original.id == later.id

    second_undo = await use_case(UndoLastCommand(user_id=user.id, source="bot"))
    assert second_undo is not None
    assert second_undo.original.id == earlier.id
    assert second_undo.original.id != later.id


async def test_nothing_to_undo_returns_none_and_commits_nothing(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    make_user: Callable[..., User],
    seed: Callable[..., None],
) -> None:
    user = make_user()
    seed(users=[user])

    use_case = UndoLastTransaction(uow_factory, clock)
    result = await use_case(UndoLastCommand(user_id=user.id, source="bot"))

    assert result is None
    assert uow_factory.store.transactions == {}
    assert uow_factory.transactions[-1].committed is False


async def test_other_sources_transactions_are_not_touched(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user()
    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    bot_transaction = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        source="bot",
    )
    scheduler_transaction = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        kind=TransactionKind.INCOME,
        source="scheduler",
    )
    seed(
        users=[user],
        accounts=[account],
        categories=[category],
        transactions=[bot_transaction, scheduler_transaction],
    )

    use_case = UndoLastTransaction(uow_factory, clock)
    result = await use_case(UndoLastCommand(user_id=user.id, source="bot"))

    assert result is not None
    assert result.original.id == bot_transaction.id

    untouched = uow_factory.store.transactions[scheduler_transaction.id]
    assert untouched.status is TransactionStatus.POSTED
    assert untouched is scheduler_transaction
