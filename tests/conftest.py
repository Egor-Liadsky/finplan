"""Общие фикстуры уровня сессии.

Раздел `docs/architecture.md`, 11.1 «Пирамида»: SQLite не используется нигде,
интеграционные тесты идут против реальной PostgreSQL 16 в контейнере
`testcontainers`, состояние между тестами откатывается вложенной транзакцией
(`SAVEPOINT`), которая не коммитится.

Тесты, которым нужен Docker, помечаются маркером ``integration``. Если Docker
недоступен на машине, такие тесты пропускаются с понятным сообщением уже на
этапе сбора — до попытки поднять контейнер; модульные тесты Docker не видят
вообще и обязаны проходить без него.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# На этой машине Docker работает через colima: путь сокета colima внутри
# host-файловой системы не совпадает с тем, что Ryuk (реапер testcontainers)
# пытается смонтировать, и `PostgresContainer().start()` падает с
# `error while creating mount source path '.../docker.sock'`. Реапер не
# обязателен для корректности тестов — контейнер запускается и
# останавливается явно через `with PostgresContainer(...) as container:` в
# фикстуре ниже; `setdefault` не переопределяет значение, если пользователь
# уже настроил его сам.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# Минимальный набор переменных раздела 10.1, при котором `Settings()`
# успешно создаётся. Значения — синтаксически корректные заглушки, не
# настоящие секреты; `TELEGRAM_BOT_TOKEN` — тот же, что уже используется как
# рабочая заглушка в `.env.example` (раздел «Решение 3» задачи
# `2026-09-22-stage0-logging-12-1-fixes.md`): `changeme` не проходит
# локальную проверку формата токена в aiogram и `Bot()` падает уже при
# импорте `finplan.entrypoints.bot.main`.
_BASELINE_ENV: dict[str, str] = {
    "APP_ENV": "local",
    "APP_BASE_URL": "http://localhost:8000",
    "DATABASE_URL": "postgresql+asyncpg://finplan:finplan@localhost:5432/finplan_placeholder",
    "TELEGRAM_BOT_TOKEN": "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
    "JWT_SECRETS": "test-secret-key-for-pytest",
    "CORS_ORIGINS": "http://localhost:5173",
}

# Несколько модулей (`entrypoints/api/app.py`, `entrypoints/bot/main.py`)
# строят объекты уровня модуля (`app = create_app()`, `bot = Bot(...)`) при
# самом импорте — то есть ещё при сборе тестов, до того как успеет
# отработать любая фикстура. `Settings()` обязана собраться уже в этот
# момент, поэтому безопасные значения по умолчанию выставляются здесь же,
# на уровне модуля `conftest.py`, который pytest импортирует раньше любого
# файла тестов. `setdefault` не трогает переменные, которые пользователь или
# CI уже определили сами.
for _key, _value in _BASELINE_ENV.items():
    os.environ.setdefault(_key, _value)


def _docker_available() -> bool:
    """Проверяет доступность Docker без попытки поднять контейнер."""
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Пропускает тесты с маркером ``integration``, если Docker недоступен.

    Намеренно проверяется `item.get_closest_marker("integration")`, а не
    `item.keywords`: последний включает и служебные ключевые слова,
    произведённые pytest из компонентов пути узла (`tests`, `integration`,
    `bot`, ...) для `-k`, поэтому тест из каталога `tests/integration/bot/`
    ловился бы этой проверкой даже без явного `pytest.mark.integration` —
    например, `tests/integration/bot/test_start.py` вообще не обращается к
    Docker и обязан выполняться и без него.
    """
    if _docker_available():
        return
    skip_docker = pytest.mark.skip(reason="Docker недоступен: тест требует testcontainers")
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip_docker)


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[Any]:
    """Поднимает PostgreSQL 16 в контейнере один раз на сессию pytest."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: Any) -> str:
    """Строка подключения (``asyncpg``) к контейнеру PostgreSQL."""
    url: str = postgres_container.get_connection_url()
    return url


def run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Запускает ``alembic`` из корня репозитория против переданной базы.

    Переменные окружения раздела 10.1 подставляются вместе с `DATABASE_URL`,
    чтобы `migrations/env.py` (через `finplan.config.get_settings()`) увидел
    рабочую конфигурацию. Падение возвращает исключение с полным
    `stdout`/`stderr` — короткого кода возврата для диагностики недостаточно.
    """
    env = {**os.environ, **_BASELINE_ENV, "DATABASE_URL": database_url}
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"'alembic {' '.join(args)}' завершился кодом {result.returncode}:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    """Применяет ``alembic upgrade head`` на контейнере один раз на сессию."""
    run_alembic(database_url, "upgrade", "head")
    return database_url


@pytest.fixture
def alembic_runner() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Даёт тестам доступ к :func:`run_alembic` через фикстуру.

    Файлы тестов под `tests/` не образуют импортируемый пакет (нет
    `__init__.py` — намеренно, раздел 2.1 дерева каталогов их не требует), а
    `import tests.conftest` из отдельного файла теста падает
    `ModuleNotFoundError` под стандартным `--import-mode=prepend` pytest.
    Фикстура — устойчивый к режиму импорта способ передать общую функцию.
    """
    return run_alembic


@pytest_asyncio.fixture
async def fresh_database_url(postgres_container: Any) -> AsyncIterator[str]:
    """Отдельная, независимая от `migrated_database` база в том же контейнере.

    Нужна тесту цикла миграций (`upgrade head` → `downgrade base` →
    `upgrade head`): он обязан начинать с абсолютно пустой схемы и не имеет
    права трогать базу, которой пользуются остальные интеграционные тесты.
    """
    admin_url = postgres_container.get_connection_url()
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    db_name = f"test_migrations_{uuid.uuid4().hex[:8]}"
    try:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{db_name}"'))
        base, _, _tail = admin_url.rpartition("/")
        fresh_url = f"{base}/{db_name}"
        yield fresh_url
    finally:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        await admin_engine.dispose()


@pytest.fixture
def env_vars(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> dict[str, str]:
    """Минимальный набор переменных раздела 10.1 для рабочего `Settings()`.

    `DATABASE_URL` подставляется строкой подключения к смигрированному
    контейнеру; кэш `get_settings()` (`lru_cache`) сбрасывается до и после
    теста, иначе следующий тест унаследует настройки этого.
    """
    from finplan.config import get_settings

    values = {**_BASELINE_ENV, "DATABASE_URL": migrated_database}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield values
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session(migrated_database: str) -> AsyncIterator[AsyncSession]:
    """Сессия SQLAlchemy, откатывающая изменения вложенной транзакцией.

    Классический паттерн «join a session into an external transaction»:
    внешняя транзакция соединения никогда не коммитится, а сессия работает
    во вложенном `SAVEPOINT`, который сама же перезапускает после каждого
    `commit()`/`rollback()` внутри теста — так тест может звать `commit()`,
    не касаясь реальных данных в базе.
    """
    engine: AsyncEngine = create_async_engine(migrated_database)
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            await connection.begin_nested()

            session = async_sessionmaker(bind=connection, expire_on_commit=False)()

            @event.listens_for(session.sync_session, "after_transaction_end")
            def _restart_savepoint(sync_session: Any, transaction: Any) -> None:
                if transaction.nested and not transaction._parent.nested:
                    sync_session.begin_nested()

            try:
                yield session
            finally:
                await session.close()
                await outer_transaction.rollback()
    finally:
        await engine.dispose()
