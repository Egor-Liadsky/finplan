"""Интеграционные тесты `SqlAlchemyUserRepository` и Unit of Work.

`docs/architecture.md`, раздел 4.3 (таблица `users`), раздел 4.5 (поиск по
`telegram_id` через `find_user_by_telegram_id` до выставления `app.user_id`,
RLS на `users` по собственному `id`), раздел 2.2 (`DuplicateError`,
контракт `UnitOfWork`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from finplan.application.ports.repositories import DuplicateError
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.entities.user import User

pytestmark = pytest.mark.integration


class TestUserRepository:
    async def test_add_and_get_round_trip(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        async with uow_factory(user.id) as uow:
            await uow.users.add(user)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            stored = await uow.users.get(user.id)

        assert stored == user

    async def test_get_returns_none_for_unknown_id(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        async with uow_factory(user.id) as uow:
            missing = await uow.users.get(user.id)

        assert missing is None

    async def test_duplicate_telegram_id_raises(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        first = make_user()
        async with uow_factory(first.id) as uow:
            await uow.users.add(first)
            await uow.commit()

        second = make_user(telegram_id=first.telegram_id)
        with pytest.raises(DuplicateError):
            async with uow_factory(second.id) as uow:
                await uow.users.add(second)

    async def test_get_by_telegram_id_before_user_known(
        self,
        uow_factory: UnitOfWorkFactory,
        reset_app_user_id: Callable[[], Awaitable[None]],
        make_user: Callable[..., User],
    ) -> None:
        """Раздел 4.5: поиск идёт до того, как `app.user_id` выставлен.

        `uow.commit()` выше — это `RELEASE SAVEPOINT`, а не конец внешней
        транзакции соединения (докстринг `conftest.py`): `app.user_id =
        user.id` остаётся выставленным на `app_connection`, хотя
        `UnitOfWork(None)` сам его не трогает. `reset_app_user_id`
        воспроизводит реальный «чистый» контекст поиска по `telegram_id» до
        того, как пользователь известен, вместо случайного совпадения с
        оставшимся значением.
        """
        user = make_user()
        async with uow_factory(user.id) as uow:
            await uow.users.add(user)
            await uow.commit()

        await reset_app_user_id()

        async with uow_factory(None) as uow:
            found = await uow.users.get_by_telegram_id(user.telegram_id)

        assert found == user

    async def test_get_by_telegram_id_returns_none_when_missing(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        async with uow_factory(None) as uow:
            found = await uow.users.get_by_telegram_id(user.telegram_id)

        assert found is None


class TestUnitOfWork:
    async def test_commit_persists_changes(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        async with uow_factory(user.id) as uow:
            await uow.users.add(user)
            await uow.commit()

        async with uow_factory(user.id) as uow:
            stored = await uow.users.get(user.id)
        assert stored is not None

    async def test_exit_without_commit_rolls_back(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        async with uow_factory(user.id) as uow:
            await uow.users.add(user)
            # Намеренно без commit().

        async with uow_factory(user.id) as uow:
            stored = await uow.users.get(user.id)
        assert stored is None

    async def test_exception_inside_block_rolls_back(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        user = make_user()

        class _BoomError(Exception):
            pass

        with pytest.raises(_BoomError):
            async with uow_factory(user.id) as uow:
                await uow.users.add(user)
                raise _BoomError

        async with uow_factory(user.id) as uow:
            stored = await uow.users.get(user.id)
        assert stored is None

    async def test_second_commit_raises_runtime_error(
        self, uow_factory: UnitOfWorkFactory, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        async with uow_factory(user.id) as uow:
            await uow.users.add(user)
            await uow.commit()
            with pytest.raises(RuntimeError):
                await uow.commit()
