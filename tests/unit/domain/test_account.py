"""Модульные тесты `Account`.

`docs/architecture.md`, раздел 3.3, таблица `Account`: валюта операции (и,
соответственно, `opening_balance`) обязана совпадать с валютой счёта.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from finplan.domain.common.currency import RUB, USD
from finplan.domain.common.errors import InvariantViolationError
from finplan.domain.common.money import Money
from finplan.domain.entities.account import Account, AccountType


def _make_account(*, currency=RUB, opening_balance: Money | None = None) -> Account:
    return Account(
        id=uuid4(),
        user_id=uuid4(),
        name="Основная карта",
        type=AccountType.CARD,
        currency=currency,
        opening_balance=opening_balance or Money(Decimal("0"), currency),
        opened_at=date(2026, 1, 1),
    )


def test_account_with_matching_opening_balance_currency_is_accepted() -> None:
    account = _make_account(currency=RUB, opening_balance=Money(Decimal("1000.00"), RUB))
    assert account.opening_balance.currency == account.currency


def test_account_opening_balance_may_be_zero() -> None:
    """Раздел 3.3: `opening_balance` может быть нулевым."""
    account = _make_account(currency=RUB, opening_balance=Money.zero(RUB))
    assert account.opening_balance.amount == Decimal("0")


def test_account_rejects_opening_balance_in_different_currency() -> None:
    with pytest.raises(InvariantViolationError):
        _make_account(currency=RUB, opening_balance=Money(Decimal("100.00"), USD))
