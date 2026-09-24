"""Модульные тесты `GetPeriodSummary`.

`docs/architecture.md`, раздел 4.2 — суммы по категориям пересчитываются из
журнала; раздел 3.3, «Форма сторно» — сторнированная пара получает
`status = reversed` с обеих сторон и потому не попадает в агрегаты вообще
(раздел 2.2), а не потому, что суммы взаимно уничтожаются знаком.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fakes import FakeUnitOfWorkFactory, FixedClock

from finplan.application.dto.reports import PeriodSummaryQuery
from finplan.application.errors import NotFoundError
from finplan.application.use_cases.reports.period_summary import GetPeriodSummary
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import Category, CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind, TransactionStatus
from finplan.domain.entities.user import User

_MSK = ZoneInfo("Europe/Moscow")


async def test_day_and_month_periods_are_computed_in_user_timezone(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
) -> None:
    # 22:00 UTC 28 февраля — уже 01:00 по Москве 1 марта: наивная дата по UTC
    # (28 февраля) отличалась бы от правильной даты пользователя (1 марта).
    clock.set(datetime(2026, 2, 28, 22, 0, tzinfo=UTC))
    user = make_user(timezone="Europe/Moscow")
    seed(users=[user])

    use_case = GetPeriodSummary(uow_factory, clock)

    day_result = await use_case(PeriodSummaryQuery(user_id=user.id, scope="day"))
    assert day_result.start == date(2026, 3, 1)
    assert day_result.end == date(2026, 3, 2)

    month_result = await use_case(PeriodSummaryQuery(user_id=user.id, scope="month"))
    assert month_result.start == date(2026, 3, 1)
    assert month_result.end == date(2026, 4, 1)


async def test_day_boundary_from_is_included_and_to_is_excluded(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user(timezone="Europe/Moscow")
    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, slug="food", name="Еда")

    today_local = clock.now().astimezone(_MSK).date()
    tomorrow_local = today_local + timedelta(days=1)
    start_utc = datetime.combine(today_local, time.min, tzinfo=_MSK).astimezone(UTC)
    end_utc = datetime.combine(tomorrow_local, time.min, tzinfo=_MSK).astimezone(UTC)

    on_start = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("100.00"),
        occurred_at=start_utc,
    )
    on_end = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("999.00"),
        occurred_at=end_utc,
    )
    seed(users=[user], accounts=[account], categories=[category], transactions=[on_start, on_end])

    use_case = GetPeriodSummary(uow_factory, clock)
    result = await use_case(PeriodSummaryQuery(user_id=user.id, scope="day"))

    assert result.expense_total == Decimal("100.00")
    assert len(result.expenses) == 1
    assert result.expenses[0].total == Decimal("100.00")


async def test_missing_user_raises_not_found(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
) -> None:
    use_case = GetPeriodSummary(uow_factory, clock)

    with pytest.raises(NotFoundError):
        await use_case(PeriodSummaryQuery(user_id=uuid4(), scope="day"))


async def test_month_boundary_from_is_included_and_to_is_excluded(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user(timezone="Europe/Moscow")
    account = make_account(user_id=user.id)
    category = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, slug="food", name="Еда")

    today_local = clock.now().astimezone(_MSK).date()
    month_start_local = date(today_local.year, today_local.month, 1)
    next_month_start_local = (
        date(today_local.year + 1, 1, 1)
        if today_local.month == 12
        else date(today_local.year, today_local.month + 1, 1)
    )
    start_utc = datetime.combine(month_start_local, time.min, tzinfo=_MSK).astimezone(UTC)
    end_utc = datetime.combine(next_month_start_local, time.min, tzinfo=_MSK).astimezone(UTC)

    on_start = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("100.00"),
        occurred_at=start_utc,
    )
    on_end = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("999.00"),
        occurred_at=end_utc,
    )
    seed(users=[user], accounts=[account], categories=[category], transactions=[on_start, on_end])

    use_case = GetPeriodSummary(uow_factory, clock)
    result = await use_case(PeriodSummaryQuery(user_id=user.id, scope="month"))

    assert result.expense_total == Decimal("100.00")
    assert len(result.expenses) == 1
    assert result.expenses[0].total == Decimal("100.00")


async def test_subcategory_totals_roll_up_into_root_category(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user(timezone="Europe/Moscow")
    account = make_account(user_id=user.id)
    root = make_category(user_id=user.id, kind=CategoryKind.EXPENSE, slug="food", name="Еда")
    child = make_category(
        user_id=user.id, kind=CategoryKind.EXPENSE, slug="groceries", name="Продукты", parent=root
    )
    transaction = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=child.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("55.00"),
        occurred_at=clock.now(),
    )
    seed(users=[user], accounts=[account], categories=[root, child], transactions=[transaction])

    use_case = GetPeriodSummary(uow_factory, clock)
    result = await use_case(PeriodSummaryQuery(user_id=user.id, scope="day"))

    assert len(result.expenses) == 1
    assert result.expenses[0].category_id == root.id
    assert result.expenses[0].name == root.name
    assert result.expenses[0].total == Decimal("55.00")


async def test_archived_category_transactions_are_counted(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user(timezone="Europe/Moscow")
    account = make_account(user_id=user.id)
    archived_category = make_category(
        user_id=user.id, kind=CategoryKind.EXPENSE, slug="misc", name="Прочее", is_archived=True
    )
    transaction = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=archived_category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("15.00"),
        occurred_at=clock.now(),
    )
    seed(
        users=[user],
        accounts=[account],
        categories=[archived_category],
        transactions=[transaction],
    )

    use_case = GetPeriodSummary(uow_factory, clock)
    result = await use_case(PeriodSummaryQuery(user_id=user.id, scope="day"))

    assert result.expense_total == Decimal("15.00")
    assert result.expenses[0].category_id == archived_category.id


async def test_reversed_pair_contributes_zero_to_totals(
    uow_factory: FakeUnitOfWorkFactory,
    clock: FixedClock,
    seed: Callable[..., None],
    make_user: Callable[..., User],
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_transaction: Callable[..., Transaction],
) -> None:
    user = make_user(timezone="Europe/Moscow")
    account = make_account(user_id=user.id)
    reversed_category = make_category(
        user_id=user.id, kind=CategoryKind.EXPENSE, slug="travel", name="Путешествия"
    )
    kept_category = make_category(
        user_id=user.id, kind=CategoryKind.EXPENSE, slug="food", name="Еда"
    )

    posted = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=reversed_category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("500.00"),
        occurred_at=clock.now(),
        status=TransactionStatus.POSTED,
    )
    reversed_original, reversal = posted.reverse(reversal_id=uuid4(), created_at=clock.now())
    kept = make_transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=kept_category.id,
        kind=TransactionKind.EXPENSE,
        amount=Decimal("40.00"),
        occurred_at=clock.now(),
    )
    seed(
        users=[user],
        accounts=[account],
        categories=[reversed_category, kept_category],
        transactions=[reversed_original, reversal, kept],
    )

    use_case = GetPeriodSummary(uow_factory, clock)
    result = await use_case(PeriodSummaryQuery(user_id=user.id, scope="day"))

    category_ids = {item.category_id for item in result.expenses}
    assert reversed_category.id not in category_ids
    assert result.expense_total == Decimal("40.00")
