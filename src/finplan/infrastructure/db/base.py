"""``DeclarativeBase`` и соглашение об именах ограничений.

Раздел `docs/architecture.md`, 4.1 «Общие соглашения»: имена ограничений
задаются `naming_convention`, чтобы Alembic генерировал стабильные миграции
и не подбирал случайные имена для constraint без явного `name=`. Шаблоны
воспроизведены дословно из документа.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей ``infrastructure/db/models``.

    Общая `MetaData` со всеми моделями нужна, чтобы `Alembic` собирал
    `target_metadata` одним импортом пакета `models` и видел все таблицы для
    автогенерации и `alembic check`.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
