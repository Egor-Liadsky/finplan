"""Модульные тесты `ListAccounts`."""

from __future__ import annotations

from collections.abc import Callable

from fakes import FakeUnitOfWorkFactory

from finplan.application.dto.accounts import ListAccountsQuery
from finplan.application.use_cases.accounts.list_accounts import ListAccounts
from finplan.domain.entities.account import Account
from finplan.domain.entities.user import User


async def test_archived_accounts_are_excluded_and_foreign_accounts_are_not_visible(
    uow_factory: FakeUnitOfWorkFactory,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
) -> None:
    owner = make_user()
    stranger = make_user()
    active = make_account(user_id=owner.id, name="Активный")
    archived = make_account(user_id=owner.id, name="Архивный", is_archived=True)
    foreign = make_account(user_id=stranger.id, name="Чужой")
    seed(users=[owner, stranger], accounts=[active, archived, foreign])

    use_case = ListAccounts(uow_factory)
    result = await use_case(ListAccountsQuery(user_id=owner.id))

    ids = {item.id for item in result.items}
    assert ids == {active.id}
