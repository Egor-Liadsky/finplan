"""Установка `app.user_id` для Row Level Security в текущей транзакции.

`docs/architecture.md`, раздел 4.5 «Изоляция данных на уровне БД»:
приложение подключается ролью без `BYPASSRLS` и в начале каждой транзакции
выполняет установку `app.user_id`, локальную для транзакции.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_current_user(session: AsyncSession, user_id: UUID) -> None:
    """Выставляет `app.user_id` для текущей транзакции сессии.

    Выполняется через `SELECT set_config('app.user_id', :user_id, true)`, а
    не `SET LOCAL app.user_id = :user_id`: `SET LOCAL` не принимает
    bind-параметров, а подстановка значения в текст SQL открыла бы
    инъекцию. Третий аргумент `set_config` — `true` — делает значение
    локальным для транзакции, как `SET LOCAL` (раздел 4.5).
    """
    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )
