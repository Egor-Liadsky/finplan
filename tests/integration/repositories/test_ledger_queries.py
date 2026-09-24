"""Интеграционные тесты `SqlAlchemyLedgerQueries`.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции» (`ledger` учитывает только `posted`, пара «исходная запись и
сторно» в отчёты не попадает); раздел 3.1 (`Money`/`Decimal`, точность
`numeric(20, 4)`); раздел 4.3 (таблица `transactions`); раздел 11.2
(контрольные примеры для финансовых расчётов, сверенные вручную).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import (
    Transaction,
    TransactionKind,
    TransactionStatus,
)
from finplan.domain.entities.user import User

pytestmark = pytest.mark.integration


async def _setup_owner(
    uow_factory: UnitOfWorkFactory,
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> tuple[User, Account, Account, Category, Category]:
    """Пользователь с двумя счетами и категориями обоих видов."""
    user = make_user()
    async with uow_factory(user.id) as uow:
        await uow.users.add(user)
        await uow.commit()

    account_a = make_account(user_id=user.id, name="Счёт A")
    account_b = make_account(user_id=user.id, name="Счёт B")
    expense_category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, slug="food")
    income_category = make_category(user_id=user.id, kind=CategoryKind.INCOME, slug="salary")
    async with uow_factory(user.id) as uow:
        await uow.accounts.add(account_a)
        await uow.accounts.add(account_b)
        await uow.categories.add_many([expense_category, income_category])
        await uow.commit()

    return user, account_a, account_b, expense_category, income_category


class TestAccountMovements:
    """Раздел 5.7/2.2: сумма движений по счёту в валюте счёта."""

    async def test_income_adds_expense_and_transfer_subtract_with_decimal_precision(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account_a, account_b, expense_category, income_category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        income = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=income_category.id,
            kind=TransactionKind.INCOME,
            amount=Decimal("500.1234"),
        )
        expense = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("120.5000"),
        )
        transfer = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=None,
            kind=TransactionKind.TRANSFER,
            counter_account_id=account_b.id,
            amount=Decimal("50.0000"),
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(income)
            await uow.transactions.add(expense)
            await uow.transactions.add(transfer)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            movements = await uow.ledger.account_movements(user.id)

        # Контрольный пример (раздел 11.2): 500.1234 - 120.5000 - 50.0000,
        # сравнение как `Decimal` точно, без округления и без `float`.
        assert movements[account_a.id] == Decimal("329.6234")
        assert movements[account_b.id] == Decimal("50.0000")

    async def test_pending_transaction_is_excluded(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account_a, _account_b, expense_category, _income_category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        pending = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            status=TransactionStatus.PENDING,
            amount=Decimal("999.0000"),
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(pending)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            movements = await uow.ledger.account_movements(user.id)

        # Счёт без ни одной `posted`-операции не попадает в словарь вовсе
        # (докстринг порта `LedgerQueries.account_movements`).
        assert account_a.id not in movements

    async def test_reversed_pair_is_excluded_from_sum(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        """Сторнированная операция вместе со своей сторнирующей записью не
        отражается в сумме: обе получают `status = reversed` по «форме
        сторно» (раздел 3.3), а запрос учитывает только `posted`.
        """
        user, account_a, _account_b, expense_category, income_category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        kept_income = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=income_category.id,
            kind=TransactionKind.INCOME,
            amount=Decimal("1000.0000"),
        )
        to_reverse = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("400.0000"),
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(kept_income)
            await uow.transactions.add(to_reverse)
            await uow.commit()

        reversed_original, reversal = to_reverse.reverse(
            reversal_id=uuid4(), created_at=datetime(2026, 1, 16, 9, 0, tzinfo=UTC)
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.mark_reversed(user.id, reversed_original.id)
            await uow.transactions.add(reversal)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            movements = await uow.ledger.account_movements(user.id)

        # Останется только доход: сторнированный расход и его сторно (оба
        # `status = reversed`) в сумму не входят вовсе, а не взаимно
        # компенсируются нулём.
        assert movements[account_a.id] == Decimal("1000.0000")


class TestTotalsByCategory:
    """Раздел 3.1/4.1: суммы `base_amount` по категориям, полуинтервал
    `[start, end)` по `occurred_at` (раздел 3.1 «Периоды» использует тот же
    полуинтервал, что и здесь).
    """

    async def test_operation_at_start_included_at_end_excluded(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account_a, _account_b, expense_category, _income_category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        start = datetime(2026, 2, 1, tzinfo=UTC)
        end = datetime(2026, 3, 1, tzinfo=UTC)
        at_start = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("10.0000"),
            occurred_at=start,
        )
        at_end = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("20.0000"),
            occurred_at=end,
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(at_start)
            await uow.transactions.add(at_end)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            totals = await uow.ledger.totals_by_category(user.id, start, end)

        assert len(totals) == 1
        assert totals[0].category_id == expense_category.id
        assert totals[0].kind is TransactionKind.EXPENSE
        assert totals[0].base_amount == Decimal("10.0000")

    async def test_excludes_uncategorized_non_posted_and_transfer(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account_a, account_b, expense_category, income_category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        start = datetime(2026, 2, 1, tzinfo=UTC)
        end = datetime(2026, 3, 1, tzinfo=UTC)
        moment = datetime(2026, 2, 15, tzinfo=UTC)
        counted = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("30.0000"),
            occurred_at=moment,
        )
        pending = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            status=TransactionStatus.PENDING,
            amount=Decimal("999.0000"),
            occurred_at=moment,
        )
        transfer = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=None,
            kind=TransactionKind.TRANSFER,
            counter_account_id=account_b.id,
            amount=Decimal("777.0000"),
            occurred_at=moment,
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(counted)
            await uow.transactions.add(pending)
            await uow.transactions.add(transfer)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            totals = await uow.ledger.totals_by_category(user.id, start, end)

        assert len(totals) == 1
        assert totals[0].category_id == expense_category.id
        assert totals[0].base_amount == Decimal("30.0000")
        # `income_category` не участвовала ни в одной операции — её нет в
        # выдаче вовсе, как и категории без операций у `expense_category`.
        assert income_category.id not in {total.category_id for total in totals}

    async def test_income_and_expense_are_separated(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account_a, _account_b, expense_category, income_category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        start = datetime(2026, 2, 1, tzinfo=UTC)
        end = datetime(2026, 3, 1, tzinfo=UTC)
        moment = datetime(2026, 2, 10, tzinfo=UTC)
        income_one = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=income_category.id,
            kind=TransactionKind.INCOME,
            amount=Decimal("100.0000"),
            occurred_at=moment,
        )
        income_two = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=income_category.id,
            kind=TransactionKind.INCOME,
            amount=Decimal("50.5000"),
            occurred_at=moment,
        )
        expense_one = make_transaction(
            user_id=user.id,
            account_id=account_a.id,
            category_id=expense_category.id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("40.2500"),
            occurred_at=moment,
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(income_one)
            await uow.transactions.add(income_two)
            await uow.transactions.add(expense_one)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            totals = await uow.ledger.totals_by_category(user.id, start, end)

        by_category = {(total.category_id, total.kind): total.base_amount for total in totals}
        assert by_category[(income_category.id, TransactionKind.INCOME)] == Decimal("150.5000")
        assert by_category[(expense_category.id, TransactionKind.EXPENSE)] == Decimal("40.2500")
