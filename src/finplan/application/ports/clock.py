"""Порт `Clock`: источник текущего времени для use case.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»: у домена нет часов, use case берёт текущее время отсюда.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Источник текущего момента времени."""

    def now(self) -> datetime:
        """Возвращает текущий момент времени с таймзоной UTC."""
        ...
