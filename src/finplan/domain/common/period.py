"""Value object `Period`: полуинтервал дат `[start, end)`.

`docs/architecture.md`, раздел 2.1 (комментарий к `period.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from finplan.domain.common.errors import InvariantViolationError


@dataclass(frozen=True, slots=True)
class Period:
    """Полуинтервал дат: `start` включена, `end` не включена."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if not self.start < self.end:
            raise InvariantViolationError(
                f"начало периода должно быть раньше конца: {self.start} >= {self.end}"
            )

    def contains(self, value: date) -> bool:
        """Принадлежит ли `value` полуинтервалу `[start, end)`."""
        return self.start <= value < self.end

    @classmethod
    def for_day(cls, day: date) -> Period:
        """Период, покрывающий ровно один календарный день."""
        return cls(start=day, end=day + timedelta(days=1))

    @classmethod
    def for_month(cls, year: int, month: int) -> Period:
        """Период, покрывающий ровно один календарный месяц."""
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
        return cls(start=start, end=end)
