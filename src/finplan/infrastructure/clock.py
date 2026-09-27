"""Реализация порта `Clock` поверх системных часов.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»: `now()` возвращает `datetime` с таймзоной UTC. В тестах порт
подменяется фиксированными часами.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING


class SystemClock:
    """Текущее время из системных часов в UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


if TYPE_CHECKING:
    from finplan.application.ports.clock import Clock

    _check_clock: type[Clock] = SystemClock
