"""Параметризованная проверка изоляции пользователей по разделу 11.4.

`docs/architecture.md`, раздел 11.4 (дословно в `docs/architecture-brief.md`):
«параметризованный тест перебирает все публичные методы и требует, чтобы
чужие данные не возвращались». Раздел 4.5 (RLS, роли `finplan_app`/
`finplan_worker`, ADR-008 — репозиторий фильтрует по `user_id` явно поверх
RLS); раздел 4.3 (таблица `transactions`).

Список методов собирается через `inspect`/`vars()` по самим классам
репозиториев и `SqlAlchemyLedgerQueries`, а не переписывается руками: новый
публичный метод появляется в параметрах теста автоматически. У каждого
метода в `CHECKS` обязана быть запись — иначе `test_method_has_no_leak`
явно падает (`pytest.fail`), а не пропускается, следуя тексту задания:
«метод, для которого способ проверки не описан в таблице теста, должен
ронять тест, а не пропускаться молча».
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import (
    Transaction,
    TransactionStatus,
)
from finplan.domain.entities.user import User
from finplan.infrastructure.db.queries.ledger import SqlAlchemyLedgerQueries
from finplan.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from finplan.infrastructure.db.repositories.categories import SqlAlchemyCategoryRepository
from finplan.infrastructure.db.repositories.transactions import SqlAlchemyTransactionRepository
from finplan.infrastructure.db.repositories.users import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration


# --- Автоматический сбор публичных методов -----------------------------
#
# Имя атрибута на `UnitOfWork` (раздел 2.2: `users`, `accounts`,
# `categories`, `transactions`, `ledger`) сопоставлено классу реализации.

_REPO_CLASSES: dict[str, type] = {
    "users": SqlAlchemyUserRepository,
    "accounts": SqlAlchemyAccountRepository,
    "categories": SqlAlchemyCategoryRepository,
    "transactions": SqlAlchemyTransactionRepository,
    "ledger": SqlAlchemyLedgerQueries,
}


def _public_methods(cls: type) -> list[str]:
    return sorted(
        name
        for name, member in vars(cls).items()
        if not name.startswith("_") and inspect.iscoroutinefunction(member)
    )


ALL_METHODS: list[tuple[str, str]] = [
    (attr, method) for attr, cls in _REPO_CLASSES.items() for method in _public_methods(cls)
]


# --- Мир теста: владелец A, сосед B и данные A --------------------------


@dataclass(frozen=True, slots=True)
class World:
    owner: User
    neighbour: User
    account: Account
    category: Category
    transaction: Transaction
    # Доменные объекты, которые никогда не сохранялись — нужны, чтобы
    # проверить методы `add`/`add_many` попыткой создать строку от чужого
    # имени; в БД их быть не должно ни до, ни после проверки.
    hostile_user: User
    hostile_account: Account
    hostile_category: Category
    hostile_transaction: Transaction


@pytest.fixture
async def world(
    uow_factory: UnitOfWorkFactory,
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> World:
    owner = make_user()
    neighbour = make_user()
    async with uow_factory(owner.id) as uow:
        await uow.users.add(owner)
        await uow.commit()
    async with uow_factory(neighbour.id) as uow:
        await uow.users.add(neighbour)
        await uow.commit()

    account = make_account(user_id=owner.id)
    category = make_category(user_id=owner.id, kind=CategoryKind.EXPENSE)
    async with uow_factory(owner.id) as uow:
        await uow.accounts.add(account)
        await uow.categories.add_many([category])
        await uow.commit()

    transaction = make_transaction(
        user_id=owner.id,
        account_id=account.id,
        category_id=category.id,
        source="bot",
    )
    async with uow_factory(owner.id) as uow:
        await uow.transactions.add(transaction)
        await uow.commit()

    return World(
        owner=owner,
        neighbour=neighbour,
        account=account,
        category=category,
        transaction=transaction,
        hostile_user=make_user(),
        hostile_account=make_account(user_id=owner.id),
        hostile_category=make_category(user_id=owner.id, kind=CategoryKind.EXPENSE),
        hostile_transaction=make_transaction(
            user_id=owner.id,
            account_id=account.id,
            category_id=category.id,
            source="bot",
        ),
    )


def _assert_blocked_by_rls(exc: BaseException) -> None:
    """RLS `USING`/`WITH CHECK` на `finplan_app` отклоняет строку кодом
    `42501` (`insufficient_privilege`, см. `migrations/versions/
    20260924_1600-d6cb2637f739_grant_privileges_and_rls.py`), а не тихо
    молчит и не путается с `DuplicateError` (`23505`).
    """
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None)
    assert sqlstate == "42501", f"ожидали блокировку RLS (42501), получили {exc!r}"


Checker = Callable[[UnitOfWorkFactory, World], Awaitable[None]]


async def _users_get(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.users.get(world.owner.id)
    assert result is None


async def _users_get_by_telegram_id(uow_factory: UnitOfWorkFactory, world: World) -> None:
    """Раздел 4.5: поиск по `telegram_id` обслуживает вход до аутентификации
    и намеренно идёт через `SECURITY DEFINER` функцию `find_user_by_
    telegram_id`, минуя `app.user_id` текущего `UnitOfWork` — точно так, как
    описано в докстринге `SqlAlchemyUserRepository.get_by_telegram_id`.
    Изоляция по «чужому» `UnitOfWork` к этому методу неприменима по
    архитектуре, а не пропущена по недосмотру; проверяем, что метод и
    правда находит пользователя независимо от того, чей `UnitOfWork`
    открыт, — документированное исключение, а не молчаливый пропуск.
    """
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.users.get_by_telegram_id(world.owner.telegram_id)
    assert result is not None
    assert result.id == world.owner.id


async def _users_add(uow_factory: UnitOfWorkFactory, world: World) -> None:
    """`p_users_self` — `WITH CHECK (id = app.user_id)`: сосед B не может
    создать строку `users` ни под чужим, ни под третьим `id`.
    """
    with pytest.raises(DBAPIError) as exc_info:
        async with uow_factory(world.neighbour.id) as uow:
            await uow.users.add(world.hostile_user)
            await uow.commit()
    _assert_blocked_by_rls(exc_info.value)


async def _accounts_get(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.accounts.get(world.neighbour.id, world.account.id)
    assert result is None


async def _accounts_list(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.accounts.list(world.neighbour.id, include_archived=True)
    assert all(account.id != world.account.id for account in result)


async def _accounts_add(uow_factory: UnitOfWorkFactory, world: World) -> None:
    """`p_accounts_owner` — та же `USING`-клауза действует и как
    `WITH CHECK` для `INSERT` (без явного `WITH CHECK` PostgreSQL переиспользует
    `USING`): сосед B не может вставить счёт с `user_id = owner.id`.
    """
    with pytest.raises(DBAPIError) as exc_info:
        async with uow_factory(world.neighbour.id) as uow:
            await uow.accounts.add(world.hostile_account)
            await uow.commit()
    _assert_blocked_by_rls(exc_info.value)


async def _categories_get(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.categories.get(world.neighbour.id, world.category.id)
    assert result is None


async def _categories_list(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.categories.list(
            world.neighbour.id, CategoryKind.EXPENSE, include_archived=True
        )
    assert all(category.id != world.category.id for category in result)


async def _categories_add_many(uow_factory: UnitOfWorkFactory, world: World) -> None:
    with pytest.raises(DBAPIError) as exc_info:
        async with uow_factory(world.neighbour.id) as uow:
            await uow.categories.add_many([world.hostile_category])
            await uow.commit()
    _assert_blocked_by_rls(exc_info.value)


async def _transactions_get(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.transactions.get(world.neighbour.id, world.transaction.id)
    assert result is None


async def _transactions_add(uow_factory: UnitOfWorkFactory, world: World) -> None:
    with pytest.raises(DBAPIError) as exc_info:
        async with uow_factory(world.neighbour.id) as uow:
            await uow.transactions.add(world.hostile_transaction)
            await uow.commit()
    _assert_blocked_by_rls(exc_info.value)


async def _transactions_mark_reversed(uow_factory: UnitOfWorkFactory, world: World) -> None:
    """`mark_reversed` с чужим `user_id` в `WHERE` не находит строку A и не
    меняет её — молча ноль обновлённых строк, а не ошибка (раздел 4.2).
    """
    async with uow_factory(world.neighbour.id) as uow:
        await uow.transactions.mark_reversed(world.neighbour.id, world.transaction.id)
        await uow.commit()

    async with uow_factory(world.owner.id) as uow:
        still_posted = await uow.transactions.get(world.owner.id, world.transaction.id)
    assert still_posted is not None
    assert still_posted.status is TransactionStatus.POSTED


async def _transactions_last_reversible(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        result = await uow.transactions.last_reversible(world.neighbour.id, "bot")
    assert result is None


async def _ledger_account_movements(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        movements = await uow.ledger.account_movements(world.neighbour.id)
    assert world.account.id not in movements


async def _ledger_totals_by_category(uow_factory: UnitOfWorkFactory, world: World) -> None:
    async with uow_factory(world.neighbour.id) as uow:
        totals = await uow.ledger.totals_by_category(
            world.neighbour.id,
            datetime(2000, 1, 1, tzinfo=UTC),
            datetime(2100, 1, 1, tzinfo=UTC),
        )
    assert world.category.id not in {total.category_id for total in totals}


CHECKS: dict[tuple[str, str], Checker] = {
    ("users", "get"): _users_get,
    ("users", "get_by_telegram_id"): _users_get_by_telegram_id,
    ("users", "add"): _users_add,
    ("accounts", "get"): _accounts_get,
    ("accounts", "list"): _accounts_list,
    ("accounts", "add"): _accounts_add,
    ("categories", "get"): _categories_get,
    ("categories", "list"): _categories_list,
    ("categories", "add_many"): _categories_add_many,
    ("transactions", "get"): _transactions_get,
    ("transactions", "add"): _transactions_add,
    ("transactions", "mark_reversed"): _transactions_mark_reversed,
    ("transactions", "last_reversible"): _transactions_last_reversible,
    ("ledger", "account_movements"): _ledger_account_movements,
    ("ledger", "totals_by_category"): _ledger_totals_by_category,
}


class TestTenantIsolation:
    """Раздел 11.4: сосед B не получает данные владельца A ни одним
    публичным методом ни одного из пяти классов доступа к данным.
    """

    @pytest.mark.parametrize(
        ("attr", "method"), ALL_METHODS, ids=[f"{attr}.{method}" for attr, method in ALL_METHODS]
    )
    async def test_method_does_not_leak_data(
        self,
        attr: str,
        method: str,
        uow_factory: UnitOfWorkFactory,
        world: World,
    ) -> None:
        checker = CHECKS.get((attr, method))
        if checker is None:
            pytest.fail(
                f"нет описанной проверки изоляции для {attr}.{method}: "
                "добавьте запись в CHECKS раздела test_tenant_isolation.py, "
                "а не пропускайте новый метод молча (раздел 11.4)"
            )
        await checker(uow_factory, world)


class TestRowLevelSecurityDirectSelect:
    """Раздел 4.5: без явного фильтра по `user_id` в запросе чужие строки
    отсекает сама RLS-политика, а не код репозитория.
    """

    async def test_direct_select_from_transactions_hides_other_users_rows(
        self,
        uow_factory: UnitOfWorkFactory,
        app_connection: AsyncConnection,
        world: World,
    ) -> None:
        # `world.transaction` уже вставлена и закоммичена (в смысле
        # `RELEASE SAVEPOINT`) от имени владельца на `app_connection` —
        # физически строка существует на этом соединении.
        await app_connection.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(world.neighbour.id)},
        )
        rows = (await app_connection.execute(text("SELECT id FROM transactions"))).all()
        assert world.transaction.id not in {row.id for row in rows}

        # Контроль: под `app.user_id` владельца та же строка без `WHERE`
        # видна — значит "не видно" выше объясняется именно RLS, а не тем,
        # что данных физически ещё нет.
        await app_connection.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(world.owner.id)},
        )
        owner_rows = (await app_connection.execute(text("SELECT id FROM transactions"))).all()
        assert world.transaction.id in {row.id for row in owner_rows}
