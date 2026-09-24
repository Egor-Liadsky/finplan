"""Цикл миграций и сверка схемы с метаданными SQLAlchemy.

Раздел `docs/architecture.md`, 11.5 «Прочее»: `upgrade head` → `downgrade
base` → `upgrade head` на чистой базе, и отдельно `alembic check` против
метаданных `Base.metadata`. Каждый тест получает собственную базу данных
внутри общего контейнера (`fresh_database_url`), не пересекающуюся с базой,
которой пользуются остальные интеграционные тесты (`migrated_database`) —
цикл обязан начинаться с пустой схемы и не имеет права портить состояние
чужих тестов.
"""

from __future__ import annotations

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
