"""Модульные тесты `ListCategories`."""

from __future__ import annotations

from collections.abc import Callable

from fakes import FakeUnitOfWorkFactory

from finplan.application.dto.categories import ListCategoriesQuery
from finplan.application.use_cases.categories.list_categories import ListCategories
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.user import User


async def test_archived_and_foreign_and_wrong_kind_categories_are_excluded(
    uow_factory: FakeUnitOfWorkFactory,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_category: Callable[..., Category],
) -> None:
    owner = make_user()
    stranger = make_user()
    active_expense = make_category(user_id=owner.id, kind=CategoryKind.EXPENSE, slug="food")
    archived_expense = make_category(
        user_id=owner.id, kind=CategoryKind.EXPENSE, slug="misc", is_archived=True
    )
    income = make_category(user_id=owner.id, kind=CategoryKind.INCOME, slug="salary")
    foreign_expense = make_category(user_id=stranger.id, kind=CategoryKind.EXPENSE, slug="food")
    seed(
        users=[owner, stranger],
        categories=[active_expense, archived_expense, income, foreign_expense],
    )

    use_case = ListCategories(uow_factory)
    result = await use_case(ListCategoriesQuery(user_id=owner.id, kind=CategoryKind.EXPENSE))

    ids = {item.id for item in result.items}
    assert ids == {active_expense.id}
