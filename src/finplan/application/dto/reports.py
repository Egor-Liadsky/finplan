"""DTO отчётов по периодам.

`docs/architecture.md`, раздел 3.3 (`Category`, поле `depth`) и раздел 4.2
(агрегаты — производные величины, пересчитываемые из журнала).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from finplan.application.dto.base import Dto


class PeriodSummaryQuery(Dto):
    """Запрос свода доходов и расходов за день или месяц."""

    user_id: UUID
    scope: Literal["day", "month"]


class CategoryTotalDTO(Dto):
    """Сумма по одной корневой категории (`depth = 0`)."""

    category_id: UUID
    name: str
    total: Decimal


class PeriodSummaryDTO(Dto):
    """Результат `PeriodSummaryQuery`: свод за полуинтервал `[start, end)`.

    `start` и `end` — даты в таймзоне пользователя; суммы по категориям
    свёрнуты до корневых категорий.
    """

    start: date
    end: date
    currency: str
    expense_total: Decimal
    income_total: Decimal
    expenses: tuple[CategoryTotalDTO, ...]
    incomes: tuple[CategoryTotalDTO, ...]
