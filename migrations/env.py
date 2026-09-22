"""Точка входа Alembic: async engine, строка подключения — из ``Settings``.

Раздел `docs/architecture.md`, 10.2 «Файлы настроек»: URL БД не хранится в
`alembic.ini`, читается здесь через `finplan.config.get_settings()`, поэтому
пароль не попадает в файл, отслеживаемый git. Раздел 10.4 «Миграции при
старте»: `alembic upgrade head` — отдельная команда деплоя, эта точка входа
не вызывается автоматически при старте приложения.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from finplan.config import get_settings
from finplan.infrastructure.db import models
from finplan.infrastructure.db.base import Base
from finplan.infrastructure.db.engine import create_engine

# Импорт пакета models выше регистрирует все ORM-модели в Base.metadata;
# имя сохраняется, чтобы ruff не счёл импорт неиспользуемым.
_ = models

# Объект Config из alembic.ini, доступный внутри env.py.
config = context.config

# Настройка логирования Alembic из секций [loggers]/[handlers]/... alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata собирается импортом finplan.infrastructure.db.models выше:
# он подтягивает Currency, User и любые другие модели, зарегистрированные
# в infrastructure/db/models/__init__.py.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Режим offline: рендерит SQL в вывод без подключения к БД."""
    context.configure(
        url=get_settings().database.dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Режим online: создаёт async engine из ``Settings`` и подключается к БД."""
    connectable: AsyncEngine = create_engine(get_settings().database)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
