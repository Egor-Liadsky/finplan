"""Форматирование дат и периодов для сообщений бота.

`docs/architecture.md`, раздел 6.5: даты показываются в привычном
пользователю формате `дд.мм.гггг`, периоды отчётов — как полуинтервал
`[start, end)`.
"""

from __future__ import annotations

from datetime import date, timedelta

_MONTHS_NOMINATIVE = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)


def format_date(d: date) -> str:
    """Форматирует дату как `24.09.2026`."""
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"


def format_period(start: date, end: date) -> str:
    """Форматирует полуинтервал `[start, end)`.

    Один день — `format_date(start)`; ровно календарный месяц — название
    месяца в именительном падеже со строчной буквы и год; иначе диапазон
    `start` — `end - 1 день` через « — ».
    """
    if end - start == timedelta(days=1):
        return format_date(start)
    if start.day == 1 and end == _first_day_of_next_month(start):
        return f"{_MONTHS_NOMINATIVE[start.month - 1]} {start.year}"
    return f"{format_date(start)} — {format_date(end - timedelta(days=1))}"


def _first_day_of_next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)
