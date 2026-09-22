"""Фабрики async engine и sessionmaker поверх ``asyncpg``.

Ни одна из функций не читает окружение и не вызывает
`finplan.config.get_settings` сама: строка подключения и параметры пула
передаются аргументом, чтобы вызывающий код (`container.py`, тесты) мог
подставить произвольную БД без переменных окружения процесса.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from finplan.config import DatabaseSettings

_DEFAULT_POOL_SIZE = 10
_DEFAULT_MAX_OVERFLOW = 5
_DEFAULT_ECHO = False


def create_engine(
    database: DatabaseSettings | str,
    *,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    echo: bool | None = None,
) -> AsyncEngine:
    """Создаёт async engine поверх ``asyncpg``.

    ``database`` — секция :class:`DatabaseSettings` (тогда параметры пула по
    умолчанию берутся из `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`,
    `DATABASE_ECHO`) либо готовая строка подключения (тогда действуют
    значения по умолчанию модуля, которые можно переопределить именованными
    аргументами) — например, для подмены на тестовую БД без чтения `.env`.
    Именованные аргументы всегда имеют приоритет над `database`.
    """
    if isinstance(database, str):
        url = database
        base_pool_size = _DEFAULT_POOL_SIZE
        base_max_overflow = _DEFAULT_MAX_OVERFLOW
        base_echo = _DEFAULT_ECHO
    else:
        url = database.dsn()
        base_pool_size = database.pool_size
        base_max_overflow = database.max_overflow
        base_echo = database.echo

    return create_async_engine(
        url,
        pool_size=pool_size if pool_size is not None else base_pool_size,
        max_overflow=max_overflow if max_overflow is not None else base_max_overflow,
        echo=echo if echo is not None else base_echo,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создаёт ``async_sessionmaker`` с ``expire_on_commit=False``."""
    return async_sessionmaker(engine, expire_on_commit=False)
