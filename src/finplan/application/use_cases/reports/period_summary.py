"""Use case `GetPeriodSummary`: свод доходов и расходов за день или месяц.

`docs/architecture.md`, раздел 6.1 (`/today`, `/month`) и раздел 4.2 — суммы
по категориям пересчитываются из журнала, а не хранятся.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from finplan.application.dto.reports import (
    CategoryTotalDTO,
    PeriodSummaryDTO,
    PeriodSummaryQuery,
)
from finplan.application.errors import NotFoundError
from finplan.application.ports.clock import Clock
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.common.period import Period
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import TransactionKind

#: Накопленная сумма и отображаемое имя одной корневой категории.
_RootTotal = tuple[str, Decimal]


class GetPeriodSummary:
    """Свод доходов и расходов по корневым категориям за день или месяц."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def __call__(self, query: PeriodSummaryQuery) -> PeriodSummaryDTO:
        async with self._uow_factory(query.user_id) as uow:
            user = await uow.users.get(query.user_id)
            if user is None:
                raise NotFoundError(f"пользователь {query.user_id} не найден")

            timezone = ZoneInfo(user.timezone)
            today = self._clock.now().astimezone(timezone).date()
            period = (
                Period.for_day(today)
                if query.scope == "day"
                else Period.for_month(today.year, today.month)
            )
            start = datetime.combine(period.start, time.min, tzinfo=timezone).astimezone(UTC)
            end = datetime.combine(period.end, time.min, tzinfo=timezone).astimezone(UTC)

            totals = await uow.ledger.totals_by_category(query.user_id, start, end)
            expense_categories = await uow.categories.list(
                query.user_id, CategoryKind.EXPENSE, include_archived=True
            )
            income_categories = await uow.categories.list(
                query.user_id, CategoryKind.INCOME, include_archived=True
            )

        categories_by_id: dict[UUID, Category] = {
            category.id: category for category in (*expense_categories, *income_categories)
        }

        expense_roots: dict[UUID, _RootTotal] = {}
        income_roots: dict[UUID, _RootTotal] = {}
        for total in totals:
            category = categories_by_id.get(total.category_id)
            if category is None:
                raise NotFoundError(f"категория {total.category_id} не найдена")
            root = category
            while root.parent_id is not None:
                root = categories_by_id[root.parent_id]
            roots = expense_roots if total.kind == TransactionKind.EXPENSE else income_roots
            name, amount = roots.get(root.id, (root.name, Decimal(0)))
            roots[root.id] = (name, amount + total.base_amount)

        expenses = _sorted_totals(expense_roots)
        incomes = _sorted_totals(income_roots)
        expense_total = sum((amount for _, amount in expense_roots.values()), Decimal(0))
        income_total = sum((amount for _, amount in income_roots.values()), Decimal(0))

        return PeriodSummaryDTO(
            start=period.start,
            end=period.end,
            currency=user.base_currency.code,
            expense_total=expense_total,
            income_total=income_total,
            expenses=expenses,
            incomes=incomes,
        )


def _sorted_totals(roots: dict[UUID, _RootTotal]) -> tuple[CategoryTotalDTO, ...]:
    """Сортирует суммы по корневым категориям: убывание суммы, при равенстве — имя."""
    items = [
        CategoryTotalDTO(category_id=root_id, name=name, total=amount)
        for root_id, (name, amount) in roots.items()
    ]
    items.sort(key=lambda item: (-item.total, item.name))
    return tuple(items)
