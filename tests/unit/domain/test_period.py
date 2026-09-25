"""Модульные тесты `Period`: полуинтервал дат `[start, end)`.

`docs/architecture.md`, раздел 2.1 (комментарий к `period.py`) и раздел 5.1
про соглашения о подсчёте дней, которые опираются на полуинтервал. Отдельно
закрыты граничные даты: переход через границу года (декабрь) и високосный
февраль (раздел 11 задания тестировщика).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from finplan.domain.common.errors import InvariantViolationError
from finplan.domain.common.period import Period


def test_start_is_included_end_is_excluded() -> None:
    period = Period(start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert period.contains(date(2026, 1, 1)) is True
    assert period.contains(date(2026, 1, 30)) is True
    assert period.contains(date(2026, 1, 31)) is False


def test_day_before_start_is_excluded() -> None:
    period = Period(start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert period.contains(date(2025, 12, 31)) is False


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 1, 1), date(2026, 1, 1)),
        (date(2026, 1, 2), date(2026, 1, 1)),
    ],
)
def test_start_not_before_end_is_rejected(start: date, end: date) -> None:
    with pytest.raises(InvariantViolationError):
        Period(start=start, end=end)


def test_for_day_covers_exactly_one_calendar_day() -> None:
    period = Period.for_day(date(2026, 3, 15))
    assert period.start == date(2026, 3, 15)
    assert period.end == date(2026, 3, 16)
    assert period.contains(date(2026, 3, 15)) is True
    assert period.contains(date(2026, 3, 16)) is False


def test_for_month_regular_month() -> None:
    period = Period.for_month(2026, 3)
    assert period.start == date(2026, 3, 1)
    assert period.end == date(2026, 4, 1)


def test_for_month_december_crosses_year_boundary() -> None:
    """Граница года: декабрь заканчивается 1 января следующего года."""
    period = Period.for_month(2026, 12)
    assert period.start == date(2026, 12, 1)
    assert period.end == date(2027, 1, 1)
    assert period.contains(date(2026, 12, 31)) is True
    assert period.contains(date(2027, 1, 1)) is False


def test_for_month_leap_february_has_twenty_nine_days() -> None:
    """2024 — високосный год: февраль покрывает 29 дней."""
    period = Period.for_month(2024, 2)
    assert period.start == date(2024, 2, 1)
    assert period.end == date(2024, 3, 1)
    assert (period.end - period.start) == timedelta(days=29)
    assert period.contains(date(2024, 2, 29)) is True


def test_for_month_non_leap_february_has_twenty_eight_days() -> None:
    """2026 — невисокосный год: февраль покрывает 28 дней, 29 февраля нет."""
    period = Period.for_month(2026, 2)
    assert period.start == date(2026, 2, 1)
    assert period.end == date(2026, 3, 1)
    assert (period.end - period.start) == timedelta(days=28)
    assert period.contains(date(2026, 3, 1)) is False
