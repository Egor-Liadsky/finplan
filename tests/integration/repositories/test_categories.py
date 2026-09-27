"""Интеграционные тесты `SqlAlchemyCategoryRepository`.

`docs/architecture.md`, раздел 4.3 (таблица `categories`, уникальность
`(user_id, path)`), раздел 4.5/ADR-008, раздел 11.4 (изоляция пользователей).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from uuid import uuid4

import pytest

from finplan.application.ports.repositories import DuplicateError
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.user import User

pytestmark = pytest.mark.integration


async def _register(uow_factory: UnitOfWorkFactory, user: User) -> None:
    async with uow_factory(user.id) as uow:
        await uow.users.add(user)
        await uow.commit()


class TestCategoryRepository:
    async def test_add_many_and_get_round_trip_with_parent_and_aliases(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_category: Callable[..., Category],
    ) -> None:
        user = make_user()
        await _register(uow_factory, user)
        root = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, slug="food")
        child = Category.new_child(
            id=uuid4(),
            parent=root,
            slug="groceries",
            name="Продукты",
        )
        child = replace(child, aliases=("продукты", "еда"))

        async with uow_factory(user.id) as uow:
            await uow.categories.add_many([root, child])
            await uow.commit()

        async with uow_factory(user.id) as uow:
            stored_root = await uow.categories.get(user.id, root.id)
            stored_child = await uow.categories.get(user.id, child.id)

        assert stored_root == root
        assert stored_child == child
        assert stored_child is not None
        assert stored_child.parent_id == root.id
        assert stored_child.aliases == ("продукты", "еда")

    async def test_list_filters_by_kind_and_archived(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_category: Callable[..., Category],
    ) -> None:
        user = make_user()
        await _register(uow_factory, user)
        expense = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, slug="food")
        income = make_category(user_id=user.id, kind=CategoryKind.INCOME, slug="salary")
        archived_expense = make_category(
            user_id=user.id, kind=CategoryKind.EXPENSE, slug="misc", is_archived=True
        )
        async with uow_factory(user.id) as uow:
            await uow.categories.add_many([expense, income, archived_expense])
            await uow.commit()

        async with uow_factory(user.id) as uow:
            expenses = await uow.categories.list(user.id, CategoryKind.EXPENSE)
            expenses_with_archived = await uow.categories.list(
                user.id, CategoryKind.EXPENSE, include_archived=True
            )
            incomes = await uow.categories.list(user.id, CategoryKind.INCOME)

        assert [c.id for c in expenses] == [expense.id]
        assert {c.id for c in expenses_with_archived} == {expense.id, archived_expense.id}
        assert [c.id for c in incomes] == [income.id]

    async def test_duplicate_path_raises(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_category: Callable[..., Category],
    ) -> None:
        user = make_user()
        await _register(uow_factory, user)
        first = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, slug="food")
        async with uow_factory(user.id) as uow:
            await uow.categories.add_many([first])
            await uow.commit()

        second = make_category(user_id=user.id, kind=CategoryKind.INCOME, slug="food")
        with pytest.raises(DuplicateError):
            async with uow_factory(user.id) as uow:
                await uow.categories.add_many([second])


class TestTenantIsolation:
    """Раздел 11.4: сосед B не видит категорий владельца A."""

    async def test_neighbour_does_not_see_category_via_get_or_list(
        self,
        uow_factory: UnitOfWorkFactory,
        make_user: Callable[..., User],
        make_category: Callable[..., Category],
    ) -> None:
        owner = make_user()
        neighbour = make_user()
        await _register(uow_factory, owner)
        await _register(uow_factory, neighbour)

        category = make_category(user_id=owner.id, kind=CategoryKind.EXPENSE)
        async with uow_factory(owner.id) as uow:
            await uow.categories.add_many([category])
            await uow.commit()

        async with uow_factory(neighbour.id) as uow:
            via_get = await uow.categories.get(neighbour.id, category.id)
            via_list = await uow.categories.list(
                neighbour.id, CategoryKind.EXPENSE, include_archived=True
            )

        assert via_get is None
        assert list(via_list) == []
