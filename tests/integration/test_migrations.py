"""Цикл миграций, сверка схемы с метаданными SQLAlchemy и изоляция под RLS.

Раздел `docs/architecture.md`, 11.5 «Прочее»: `upgrade head` → `downgrade
base` → `upgrade head` на чистой базе, и отдельно `alembic check` против
метаданных `Base.metadata`. Каждый тест получает собственную базу данных
внутри общего контейнера (`fresh_database_url`), не пересекающуюся с базой,
которой пользуются остальные интеграционные тесты (`migrated_database`) —
цикл обязан начинаться с пустой схемы и не имеет права портить состояние
чужих тестов.

Раздел 4.5 «Изоляция данных на уровне БД»: тесты
`Test*RowLevelSecurity` проверяют не только SQL самой миграции (это делает
цикл выше), но и её эффект под ролью `finplan_app`, на которой RLS
действительно применяется — `migrated_database`, под которой запускается
`alembic`, владеет схемой и политики обходит.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from subprocess import CompletedProcess

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

AlembicRunner = Callable[..., CompletedProcess[str]]


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )
    finally:
        await engine.dispose()


async def test_migration_cycle_upgrade_downgrade_upgrade(
    fresh_database_url: str, alembic_runner: AlembicRunner
) -> None:
    """`upgrade head`, затем `downgrade base`, затем снова `upgrade head`."""
    alembic_runner(fresh_database_url, "upgrade", "head")

    tables_after_first_upgrade = await _table_names(fresh_database_url)
    assert {
        "users",
        "currencies",
        "accounts",
        "categories",
        "transactions",
    } <= tables_after_first_upgrade

    engine = create_async_engine(fresh_database_url)
    try:
        async with engine.connect() as connection:
            currency_count = await connection.scalar(text("SELECT count(*) FROM currencies"))
    finally:
        await engine.dispose()
    assert currency_count == 9

    alembic_runner(fresh_database_url, "downgrade", "base")

    tables_after_downgrade = await _table_names(fresh_database_url)
    assert "users" not in tables_after_downgrade
    assert "currencies" not in tables_after_downgrade
    assert "accounts" not in tables_after_downgrade
    assert "categories" not in tables_after_downgrade
    assert "transactions" not in tables_after_downgrade

    # Третий шаг не должен требовать ручного вмешательства между шагами.
    alembic_runner(fresh_database_url, "upgrade", "head")

    tables_after_second_upgrade = await _table_names(fresh_database_url)
    assert {
        "users",
        "currencies",
        "accounts",
        "categories",
        "transactions",
    } <= tables_after_second_upgrade


def test_alembic_check_matches_sqlalchemy_metadata(
    fresh_database_url: str, alembic_runner: AlembicRunner
) -> None:
    """`alembic check` не находит расхождений между БД и `Base.metadata`."""
    alembic_runner(fresh_database_url, "upgrade", "head")

    # `alembic_runner` поднимает исключение при ненулевом коде возврата —
    # этого достаточно, чтобы поймать расхождение (забытую миграцию);
    # сообщение `alembic check` попадёт в текст исключения.
    alembic_runner(fresh_database_url, "check")


class TestRowLevelSecurityUnderAppRole:
    """Изоляция под ролью `finplan_app`, раздел 4.5, пункт 5 подзадачи 8b."""

    async def test_users_direct_select_empty_but_find_by_telegram_id_works(
        self, migrated_database: str, app_database_url: str
    ) -> None:
        """Без `app.user_id` прямой `SELECT` из `users` пуст под RLS.

        Функция `find_user_by_telegram_id` (`SECURITY DEFINER`) находит
        того же пользователя — она и существует для поиска до того, как
        `app.user_id` установлен (раздел 4.5).
        """
        telegram_id = uuid.uuid4().int % 1_000_000_000
        user_id = uuid.uuid4()

        owner_engine = create_async_engine(migrated_database)
        try:
            async with owner_engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO users (id, telegram_id, first_name, updated_at) "
                        "VALUES (:id, :telegram_id, 'Owner insert', now())"
                    ),
                    {"id": user_id, "telegram_id": telegram_id},
                )
        finally:
            await owner_engine.dispose()

        app_engine = create_async_engine(app_database_url)
        try:
            async with app_engine.connect() as connection:
                direct_count = await connection.scalar(text("SELECT count(*) FROM users"))
                assert direct_count == 0

                found_id = await connection.scalar(
                    text("SELECT id FROM find_user_by_telegram_id(:telegram_id)"),
                    {"telegram_id": telegram_id},
                )
                assert found_id == user_id
        finally:
            await app_engine.dispose()

    async def test_app_user_id_hides_other_users_accounts(
        self, migrated_database: str, app_database_url: str
    ) -> None:
        """С `SET LOCAL app.user_id` на пользователя A не видны счета B."""
        owner_a, owner_b = uuid.uuid4(), uuid.uuid4()
        account_a, account_b = uuid.uuid4(), uuid.uuid4()

        owner_engine = create_async_engine(migrated_database)
        try:
            async with owner_engine.begin() as connection:
                for user_id, telegram_id in (
                    (owner_a, uuid.uuid4().int % 1_000_000_000),
                    (owner_b, uuid.uuid4().int % 1_000_000_000),
                ):
                    await connection.execute(
                        text(
                            "INSERT INTO users (id, telegram_id, first_name, updated_at) "
                            "VALUES (:id, :telegram_id, 'Owner insert', now())"
                        ),
                        {"id": user_id, "telegram_id": telegram_id},
                    )
                for account_id, user_id, name in (
                    (account_a, owner_a, "Account A"),
                    (account_b, owner_b, "Account B"),
                ):
                    await connection.execute(
                        text(
                            "INSERT INTO accounts "
                            "(id, user_id, name, type, currency, opened_on, created_at) "
                            "VALUES (:id, :user_id, :name, 'cash', 'RUB', now(), now())"
                        ),
                        {"id": account_id, "user_id": user_id, "name": name},
                    )
        finally:
            await owner_engine.dispose()

        app_engine = create_async_engine(app_database_url)
        try:
            async with app_engine.connect() as connection:
                # `set_config(..., true)` — эквивалент `SET LOCAL`, но
                # параметризуемый: `SET LOCAL` не принимает bind-параметры.
                await connection.execute(
                    text("SELECT set_config('app.user_id', :user_id, true)"),
                    {"user_id": str(owner_a)},
                )
                result = await connection.execute(text("SELECT id FROM accounts"))
                visible_ids = {row[0] for row in result}
                assert visible_ids == {account_a}
                await connection.rollback()
        finally:
            await app_engine.dispose()
