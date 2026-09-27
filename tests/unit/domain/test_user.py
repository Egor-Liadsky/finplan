"""Модульные тесты `User`.

`docs/architecture.md`, раздел 3.3, таблица `User`: значения по умолчанию
(`base_currency` — `RUB`, `timezone` — `Europe/Moscow`, `locale` — `ru`) и
`telegram_id` — «уникален, неизменяем после создания». Уникальность — забота
репозитория (раздел 11.4), а неизменяемость после создания обеспечивает сам
`frozen`-датакласс: попытка присвоить новое значение — отрицательный случай.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from finplan.domain.common.currency import RUB
from finplan.domain.entities.user import User


def _make_user() -> User:
    return User(
        id=uuid4(),
        telegram_id=123456789,
        username="ivan",
        first_name="Иван",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_user_has_documented_defaults() -> None:
    """Раздел 3.3: `base_currency` по умолчанию `RUB`, `timezone` —
    `Europe/Moscow`, `locale` — `ru`, `is_active` — мягкая блокировка выкл."""
    user = _make_user()
    assert user.base_currency == RUB
    assert user.timezone == "Europe/Moscow"
    assert user.locale == "ru"
    assert user.is_active is True


def test_telegram_id_is_immutable_after_creation() -> None:
    """Раздел 3.3: `telegram_id` неизменяем после создания."""
    user = _make_user()
    with pytest.raises(dataclasses.FrozenInstanceError):
        user.telegram_id = 987654321  # type: ignore[misc]
