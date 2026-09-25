"""Сущность `User`: корень изоляции данных.

`docs/architecture.md`, раздел 3.3, таблица `User`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from finplan.domain.common.currency import RUB, Currency


@dataclass(frozen=True, slots=True)
class User:
    """Пользователь. Любая другая сущность прямо или косвенно ему принадлежит."""

    id: UUID
    telegram_id: int
    username: str | None
    first_name: str
    created_at: datetime
    base_currency: Currency = RUB
    timezone: str = "Europe/Moscow"
    locale: str = "ru"
    is_active: bool = True
