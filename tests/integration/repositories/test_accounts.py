"""Интеграционные тесты `SqlAlchemyAccountRepository`.

`docs/architecture.md`, раздел 4.3 (таблица `accounts`, частичный уникальный
индекс `uq_accounts_user_id_name` по `lower(name)` среди неархивных), раздел
4.5/ADR-008 (репозиторий фильтрует по `user_id` явно поверх RLS), раздел 11.4
(изоляция пользователей).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from finplan.application.ports.repositories import DuplicateError
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.common.currency import RUB
from finplan.domain.common.money import Money
from finplan.domain.entities.account import Account
from finplan.domain.entities.user import User

pytestmark = pytest.mark.integration


async def _register(uow_factory: UnitOfWorkFactory, user: User) -> None:
    async with uow_factory(user.id) as uow:
        await uow.users.add(user)
        await uow.commit()


class TestAccountRepository:
    async def test_add_and_get_round_trip(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
    ) -> None:
        user = make_user()
        await _register(uow_factory, user)
        # Точность Decimal по хранению — `numeric(20, 4)` (раздел 4.1): значение
        # с четырьмя знаками после запятой обязано пережить запись и чтение
        # без потери точности, даже если minor_unit валюты (RUB) — 2 знака.
        account = make_account(
            user_id=user.id,
            opening_balance=Money(amount=Decimal("1234.5678"), currency=RUB),
        )
        async with uow_factory(user.id) as uow:
            await uow.accounts.add(account)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            stored = await uow.accounts.get(user.id, account.id)

        assert stored == account
        assert stored is not None
        assert stored.opening_balance.amount == Decimal("1234.5678")

    async def test_list_round_trip_includes_all_fields(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
    ) -> None:
        user = make_user()
        await _register(uow_factory, user)
        first = make_account(user_id=user.id, name="Наличные")
        second = make_account(user_id=user.id, name="Карта")
        async with uow_factory(user.id) as uow:
            await uow.accounts.add(first)
            await uow.accounts.add(second)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            listed = await uow.accounts.list(user.id)

        # Порядок — деталь реализации (`ORDER BY sort_order, created_at`),
        # `Account` в домене не хранит `sort_order`; проверяется совпадение
        # набора и полей каждой сущности, не порядок.
        assert {a.id: a for a in listed} == {first.id: first, second.id: second}

    async def test_list_filters_archived_by_default(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
    ) -> None:
        user = make_user()
        await _register(uow_factory, user)
        active = make_account(user_id=user.id, name="Активный")
        archived = make_account(user_id=user.id, name="Архивный", is_archived=True)
        async with uow_factory(user.id) as uow:
            await uow.accounts.add(active)
            await uow.accounts.add(archived)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            default_listing = await uow.accounts.list(user.id)
            with_archived = await uow.accounts.list(user.id, include_archived=True)

        assert [a.id for a in default_listing] == [active.id]
        assert {a.id for a in with_archived} == {active.id, archived.id}

    async def test_duplicate_name_case_insensitive_raises(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
    ) -> None:
        user = make_user()
        await _register(uow_factory, user)
        first = make_account(user_id=user.id, name="Wallet")
        async with uow_factory(user.id) as uow:
            await uow.accounts.add(first)
            await uow.commit()

        second = make_account(user_id=user.id, name="wallet")
        with pytest.raises(DuplicateError):
            async with uow_factory(user.id) as uow:
                await uow.accounts.add(second)


class TestTenantIsolation:
    """Раздел 11.4: сосед B не видит счетов владельца A."""

    async def test_neighbour_does_not_see_account_via_get_or_list(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_account: Callable[..., Account],
    ) -> None:
        owner = make_user()
        neighbour = make_user()
        await _register(uow_factory, owner)
        await _register(uow_factory, neighbour)

        account = make_account(user_id=owner.id)
        async with uow_factory(owner.id) as uow:
            await uow.accounts.add(account)
            await uow.commit()

        async with uow_factory(neighbour.id) as uow:
            via_get = await uow.accounts.get(neighbour.id, account.id)
            via_list = await uow.accounts.list(neighbour.id, include_archived=True)

        assert via_get is None
        assert list(via_list) == []
