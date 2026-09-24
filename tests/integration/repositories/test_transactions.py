"""Интеграционные тесты `SqlAlchemyTransactionRepository`.

`docs/architecture.md`, раздел 4.3 (таблица `transactions`, включая
`occurred_on`), раздел 3.3 (`occurred_on` — дата в таймзоне пользователя),
раздел 4.2 (`mark_reversed` — единственное разрешённое изменение строки
журнала), раздел 4.5/ADR-008, раздел 11.4 (изоляция пользователей).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from finplan.application.ports.repositories import DuplicateError
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import (
    Transaction,
    TransactionStatus,
)
from finplan.domain.entities.user import User

pytestmark = pytest.mark.integration


async def _setup_owner(
    uow_factory: UnitOfWorkFactory,
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> tuple[User, Account, Category]:
    """Регистрирует пользователя со счётом и категорией — предпосылки FK."""
    user = make_user()
    async with uow_factory(user.id) as uow:
        await uow.users.add(user)
        await uow.commit()

    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE)
    async with uow_factory(user.id) as uow:
        await uow.accounts.add(account)
        await uow.categories.add_many([category])
        await uow.commit()

    return user, account, category


class TestTransactionRepository:
    async def test_add_and_get_round_trip(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account, category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        transaction = make_transaction(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            amount=Decimal("1234.5678"),
            comment="Проверка round trip",
            external_key="ext-1",
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(transaction)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            stored = await uow.transactions.get(user.id, transaction.id)

        assert stored == transaction
        assert stored is not None
        assert stored.amount.amount == Decimal("1234.5678")
        assert stored.base_amount == Decimal("1234.5678")

    async def test_get_returns_none_for_unknown_id(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
    ) -> None:
        user, _account, _category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        async with uow_factory(user.id) as uow:
            # `user.id` заведомо не встречается среди `id` операций.
            missing = await uow.transactions.get(user.id, user.id)
        assert missing is None

    async def test_duplicate_external_key_raises(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account, category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        first = make_transaction(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            external_key="dup-key",
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(first)
            await uow.commit()

        second = make_transaction(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            external_key="dup-key",
        )
        with pytest.raises(DuplicateError):
            async with uow_factory(user.id) as uow:
                await uow.transactions.add(second)

    async def test_occurred_on_uses_user_timezone(
        self,
        uow_factory: UnitOfWorkFactory,
        app_connection: AsyncConnection,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        """Раздел 3.3: операция в 22:30 UTC у пользователя `Europe/Moscow`
        (UTC+3) сохраняется с `occurred_on = 2026-09-24` — на дату позже,
        чем календарная дата UTC (`2026-09-23`).
        """
        user, account, category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        assert user.timezone == "Europe/Moscow"
        occurred_at = datetime(2026, 9, 23, 22, 30, tzinfo=UTC)
        transaction = make_transaction(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            occurred_at=occurred_at,
            timezone=ZoneInfo(user.timezone),
        )
        assert transaction.occurred_on == date(2026, 9, 24)

        async with uow_factory(user.id) as uow:
            await uow.transactions.add(transaction)
            await uow.commit()

        # Значением столбца прямым SQL — в том же соединении, где `commit()`
        # оставил `app.user_id = user.id` (см. докстринг conftest про
        # подводный камень `app.user_id`), поэтому RLS пропускает строку.
        column_value = await app_connection.scalar(
            text("SELECT occurred_on FROM transactions WHERE id = :id"),
            {"id": transaction.id},
        )
        assert column_value == date(2026, 9, 24)

        # И чтением сущности через репозиторий.
        async with uow_factory(user.id) as uow:
            stored = await uow.transactions.get(user.id, transaction.id)
        assert stored is not None
        assert stored.occurred_on == date(2026, 9, 24)

    async def test_mark_reversed_changes_status(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account, category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        transaction = make_transaction(
            user_id=user.id, account_id=account.id, category_id=category.id
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(transaction)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            await uow.transactions.mark_reversed(user.id, transaction.id)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            stored = await uow.transactions.get(user.id, transaction.id)
        assert stored is not None
        assert stored.status is TransactionStatus.REVERSED

    async def test_last_reversible_picks_latest_posted_by_source(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        user, account, category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        earlier = make_transaction(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            source="bot",
            created_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        )
        later = make_transaction(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            source="bot",
            created_at=datetime(2026, 1, 15, 11, 0, tzinfo=UTC),
        )
        other_source = make_transaction(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            source="web",
            created_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )
        async with uow_factory(user.id) as uow:
            await uow.transactions.add(earlier)
            await uow.transactions.add(later)
            await uow.transactions.add(other_source)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            reversible = await uow.transactions.last_reversible(user.id, "bot")
        assert reversible is not None
        assert reversible.id == later.id

        async with uow_factory(user.id) as uow:
            await uow.transactions.mark_reversed(user.id, later.id)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            reversible_after = await uow.transactions.last_reversible(user.id, "bot")
        assert reversible_after is not None
        assert reversible_after.id == earlier.id

    async def test_last_reversible_returns_none_when_nothing_to_reverse(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
    ) -> None:
        user, _account, _category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        async with uow_factory(user.id) as uow:
            reversible = await uow.transactions.last_reversible(user.id, "bot")
        assert reversible is None


class TestTenantIsolation:
    """Раздел 11.4: сосед B не видит операцию владельца A."""

    async def test_neighbour_does_not_see_transaction_via_get_or_last_reversible(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
        make_category: Callable[..., Category],
        make_transaction: Callable[..., Transaction],
    ) -> None:
        owner, account, category = await _setup_owner(
            uow_factory, make_user, make_account, make_category
        )
        neighbour = make_user()
        async with uow_factory(neighbour.id) as uow:
            await uow.users.add(neighbour)
            await uow.commit()

        transaction = make_transaction(
            user_id=owner.id, account_id=account.id, category_id=category.id, source="bot"
        )
        async with uow_factory(owner.id) as uow:
            await uow.transactions.add(transaction)
            await uow.commit()

        async with uow_factory(neighbour.id) as uow:
            via_get = await uow.transactions.get(neighbour.id, transaction.id)
            via_last_reversible = await uow.transactions.last_reversible(neighbour.id, "bot")

        assert via_get is None
        assert via_last_reversible is None
