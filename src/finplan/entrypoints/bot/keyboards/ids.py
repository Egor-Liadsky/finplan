"""Короткие идентификаторы UUID для `callback_data` кнопок.

`docs/architecture.md`, раздел 6.7, «Соглашение по `callback_data`»: полный
UUID не помещается в `callback_data` вместе с остальными полями формата
`<scope>:<action>:<id>:<page>` при лимите 64 байта, поэтому используется
хвост — последние 8 байт в base64url, 11 символов без `=`. Хвост, а не
голова: у UUIDv7 первые 6 байт — метка времени в миллисекундах, и у
категорий дефолтного набора, созданных одной транзакцией, они почти
совпадают, а в последних 8 байтах у UUIDv7 и UUIDv4 одинаково 62 случайных
бита.
"""

from __future__ import annotations

from base64 import urlsafe_b64encode
from collections.abc import Iterable
from typing import Protocol
from uuid import UUID


class _HasId(Protocol):
    """Минимальный протокол для `resolve_short_id`: доменное DTO с `id`."""

    id: UUID


def short_id(value: UUID) -> str:
    """Последние 8 байт `value` в base64url без `=` — 11 символов."""
    tail = value.bytes[-8:]
    return urlsafe_b64encode(tail).decode("ascii").rstrip("=")


def resolve_short_id[T: _HasId](short: str, items: Iterable[T]) -> T | None:
    """Находит элемент `items`, чей `short_id(item.id)` совпал с `short`.

    Возвращает `None`, если совпадений нет или их больше одного — по
    разделу 6.7 в обоих случаях кнопка считается устаревшей.
    """
    matches = [item for item in items if short_id(item.id) == short]
    if len(matches) != 1:
        return None
    return matches[0]
