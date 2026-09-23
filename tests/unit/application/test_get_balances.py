"""Модульные тесты `GetBalances`.

`docs/architecture.md`, раздел 4.2 — остаток счёта не хранится, а
пересчитывается из `opening_balance` и движений журнала.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from fakes import FakeUnitOfWorkFactory

from finplan.application.dto.accounts import GetBalancesQuery
from finplan.application.use_cases.accounts.get_balances import GetBalances
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind
from finplan.domain.entities.user import User


async def test_balance_is_opening_balance_plus_movements_and_zero_without_transactions(
    uow_factory: FakeUnitOfWorkFactory,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user()
    funded_account = make_account(user_id=user.id, opening_balance=Decimal("100.00"))
    empty_account = make_account(user_id=user.id, opening_balance=Decimal("0"))
    expense_category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    income_category = make_category(user_id=user.id, kind=CategoryKind.INCOME)
    expense = make_transaction(
        user_id=user.id,
        account_id=funded_account.id,
        category_id=expense_category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("30.00"),
    )
    income = make_transaction(
        user_id=user.id,
        account_id=funded_account.id,
        category_id=income_category.id,
        kind=TransactionKind.INCOME,
        amount=Decimal("20.00"),
    )
    seed(
        users=[user],
        accounts=[funded_account, empty_account],
        categories=[expense_category, income_category],
        transactions=[expense, income],
    )

    use_case = GetBalances(uow_factory)
    result = await use_case(GetBalancesQuery(user_id=user.id))

    balances = {item.account.id: item.balance for item in result.items}
    assert balances[funded_account.id] == Decimal("90.00")
    assert balances[empty_account.id] == Decimal("0")
    assert result.total == Decimal("90.00")
    assert result.currency == user.base_currency.code
