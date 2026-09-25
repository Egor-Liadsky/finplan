"""Модульные тесты `FindUserByTelegramId`.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»: фабрика вызывается с `user_id = None`, потому что `id`
пользователя ещё не известен.
"""

from __future__ import annotations

from collections.abc import Callable

from fakes import FakeUnitOfWorkFactory

from finplan.application.dto.auth import FindUserByTelegramIdQuery
from finplan.application.use_cases.auth.find_user import FindUserByTelegramId
from finplan.domain.entities.user import User


async def test_existing_user_is_found_by_telegram_id(
    uow_factory: FakeUnitOfWorkFactory,
    seed: Callable[..., None],
    make_user: Callable[..., User],
) -> None:
    user = make_user(telegram_id=42)
    seed(users=[user])

    use_case = FindUserByTelegramId(uow_factory)
    result = await use_case(FindUserByTelegramIdQuery(telegram_id=42))

    assert result is not None
    assert result.id == user.id
    assert result.telegram_id == 42


async def test_unknown_telegram_id_returns_none(uow_factory: FakeUnitOfWorkFactory) -> None:
    use_case = FindUserByTelegramId(uow_factory)

    result = await use_case(FindUserByTelegramIdQuery(telegram_id=999))

    assert result is None
