"""Модульные тесты `RegisterUser`.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции» (обработка `DuplicateError`); раздел 3.3, таблицы `User`,
`Account` и абзац «Дефолтный набор» под таблицей `Category`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fakes import FakeUnitOfWorkFactory, FixedClock

from finplan.application.dto.auth import RegisterUserCommand
from finplan.application.errors import InvalidCommandError
from finplan.application.use_cases.auth.register_user import RegisterUser
from finplan.domain.common.currency import RUB
from finplan.domain.common.money import Money
from finplan.domain.entities.account import Account, AccountType
from finplan.domain.entities.category import DEFAULT_CATEGORY_TREE
from finplan.domain.entities.user import User

#: Раздел 3.3, «Дефолтный набор»: 16 корней + их потомки, сумма из таблицы.
_DEFAULT_CATEGORY_COUNT = sum(1 + len(root.children) for root in DEFAULT_CATEGORY_TREE)


def _command(**overrides: Any) -> RegisterUserCommand:
    defaults: dict[str, Any] = {
        "telegram_id": 555,
        "username": "alice",
        "first_name": "Алиса",
        "base_currency": "RUB",
        "timezone": "Europe/Moscow",
        "account_name": "Наличные",
        "account_type": AccountType.CASH,
        "opening_balance": Decimal("1000.00"),
    }
    defaults.update(overrides)
    return RegisterUserCommand(**defaults)


async def test_new_user_gets_first_account_and_default_categories_with_created_true(
    uow_factory: FakeUnitOfWorkFactory, clock: FixedClock
) -> None:
    use_case = RegisterUser(uow_factory, clock)

    result = await use_case(_command())

    assert result.created is True
    assert result.user.telegram_id == 555
    assert result.account.name == "Наличные"
    assert result.account.currency == "RUB"

    stored_user = uow_factory.store.users[result.user.id]
    assert stored_user.telegram_id == 555

    stored_accounts = [
        account
        for account in uow_factory.store.accounts.values()
        if account.user_id == stored_user.id
    ]
    assert len(stored_accounts) == 1
    assert stored_accounts[0].opening_balance.amount == Decimal("1000.00")

    stored_categories = [
        category
        for category in uow_factory.store.categories.values()
        if category.user_id == stored_user.id
    ]
    assert len(stored_categories) == _DEFAULT_CATEGORY_COUNT

    assert uow_factory.transactions[-1].committed is True


async def test_repeat_registration_returns_existing_user_and_does_not_duplicate_account(
    uow_factory: FakeUnitOfWorkFactory, clock: FixedClock
) -> None:
    use_case = RegisterUser(uow_factory, clock)

    first = await use_case(_command())
    second = await use_case(_command(username="alice-again", first_name="Алиса II"))

    assert second.created is False
    assert second.user.id == first.user.id
    assert second.account.id == first.account.id

    accounts_of_user = [
        account
        for account in uow_factory.store.accounts.values()
        if account.user_id == first.user.id
    ]
    assert len(accounts_of_user) == 1


async def test_concurrent_registration_race_gives_created_false(
    uow_factory: FakeUnitOfWorkFactory, clock: FixedClock
) -> None:
    """Параллельный `/start` того же `telegram_id` успевает закоммититься
    первым: `UserRepository.add` бросает `DuplicateError` уже после того, как
    `get_by_telegram_id` в этой же транзакции вернул `None` (раздел 2.2)."""
    concurrent_user = User(
        id=uuid4(),
        telegram_id=777,
        username="concurrent",
        first_name="Гонка",
        created_at=clock.now(),
        base_currency=RUB,
        timezone="Europe/Moscow",
    )
    concurrent_account = Account(
        id=uuid4(),
        user_id=concurrent_user.id,
        name="Наличные",
        type=AccountType.CASH,
        currency=RUB,
        opening_balance=Money(Decimal("0"), RUB),
        opened_at=date(2026, 1, 1),
    )
    uow_factory.store.pending_races[777] = (concurrent_user, concurrent_account)

    use_case = RegisterUser(uow_factory, clock)
    result = await use_case(_command(telegram_id=777))

    assert result.created is False
    assert result.user.id == concurrent_user.id
    assert result.account.id == concurrent_account.id


async def test_unknown_currency_code_raises_invalid_command_error(
    uow_factory: FakeUnitOfWorkFactory, clock: FixedClock
) -> None:
    use_case = RegisterUser(uow_factory, clock)

    with pytest.raises(InvalidCommandError):
        await use_case(_command(base_currency="XXX"))

    assert uow_factory.store.users == {}
    assert uow_factory.transactions == []


async def test_unknown_timezone_raises_invalid_command_error(
    uow_factory: FakeUnitOfWorkFactory, clock: FixedClock
) -> None:
    use_case = RegisterUser(uow_factory, clock)

    with pytest.raises(InvalidCommandError):
        await use_case(_command(timezone="Mars/Phobos"))
