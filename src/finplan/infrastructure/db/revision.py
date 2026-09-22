"""Проверка ревизии Alembic при старте приложения.

Раздел `docs/architecture.md`, 10.4 «Миграции при старте»: миграции — это
отдельный шаг деплоя, а не действие при старте приложения. Приложение при
старте выполняет только проверку — сравнивает текущую ревизию в
`alembic_version` с `head` из кода миграций и отказывается стартовать при
расхождении, выводя обе ревизии.

Вызывается из `api`: это единственный процесс этапа 0, который обращается к
базе. Бот и `worker` начнут вызывать проверку на этапе 1, когда у них
появится собственный engine и работа с данными; пока они к базе не ходят,
и создавать соединение только ради проверки нечего.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SCRIPT_LOCATION = _REPO_ROOT / "migrations"


class RevisionMismatchError(RuntimeError):
    """Ревизия в БД расходится с ``head`` из кода миграций."""

    def __init__(self, database_revision: str | None, head_revision: str) -> None:
        self.database_revision = database_revision
        self.head_revision = head_revision
        super().__init__(
            f"database revision is {database_revision!r}, code head is "
            f"{head_revision!r}: run 'alembic upgrade head' before starting the app"
        )


@dataclass(frozen=True, slots=True)
class RevisionStatus:
    """Пара ревизий, сравненных :func:`check_revision`."""

    database_revision: str | None
    head_revision: str


def get_head_revision(script_location: Path | str = DEFAULT_SCRIPT_LOCATION) -> str:
    """Ревизия ``head`` из файлов миграций на диске."""
    script = ScriptDirectory(str(script_location))
    head = script.get_current_head()
    if head is None:
        raise RuntimeError(f"no migrations found in {script_location}")
    return head


async def get_database_revision(connection: AsyncConnection | AsyncSession) -> str | None:
    """Текущая ревизия из таблицы ``alembic_version``.

    ``None``, если таблица ещё не создана — миграции ни разу не
    применялись к этой базе.
    """
    table_exists = await connection.scalar(
        text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
    )
    if not table_exists:
        return None
    result = await connection.execute(text("SELECT version_num FROM alembic_version"))
    row = result.first()
    return row[0] if row is not None else None


async def check_revision(
    connection: AsyncConnection | AsyncSession,
    *,
    script_location: Path | str = DEFAULT_SCRIPT_LOCATION,
) -> RevisionStatus:
    """Сравнивает ревизию БД с ``head`` из кода, поднимает исключение при расхождении.

    Возвращает обе ревизии, если они совпали.
    """
    head_revision = get_head_revision(script_location)
    database_revision = await get_database_revision(connection)
    if database_revision != head_revision:
        raise RevisionMismatchError(database_revision, head_revision)
    return RevisionStatus(database_revision, head_revision)
