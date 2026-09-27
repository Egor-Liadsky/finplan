"""Форматирование отчётов и карточек операций для сообщений бота.

`docs/architecture.md`, раздел 6.5 (карточка подтверждения) и раздел 6.6,
абзац про `parse_mode=HTML`: любой пользовательский текст — комментарий,
имена счетов и категорий — экранируется через `html.escape`. Модуль
возвращает `str` и библиотеку бота не импортирует.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from finplan.application.dto.accounts import BalancesDTO
from finplan.application.dto.reports import PeriodSummaryDTO
from finplan.application.dto.transactions import UndoResultDTO
from finplan.domain.entities.transaction import TransactionKind
from finplan.entrypoints.bot.formatters.dates import format_date, format_period
from finplan.entrypoints.bot.formatters.money import format_money


def render_balances(balances: BalancesDTO) -> str:
    """Строка на каждый счёт и итоговая строка."""
    lines = [
        f"{html.escape(item.account.name)}: {format_money(item.balance, item.account.currency)}"
        for item in balances.items
    ]
    lines.append(f"Итого: {format_money(balances.total, balances.currency)}")
    return "\n".join(lines)


def render_period_summary(summary: PeriodSummaryDTO) -> str:
    """Заголовок с периодом, итоги и разбивка по категориям по убыванию суммы."""
    lines = [format_period(summary.start, summary.end)]

    if not summary.expenses and not summary.incomes:
        lines.append("Операций за период нет.")
        return "\n".join(lines)

    lines.append(f"Расходы: {format_money(summary.expense_total, summary.currency)}")
    for item in sorted(summary.expenses, key=lambda c: c.total, reverse=True):
        lines.append(f"  {html.escape(item.name)}: {format_money(item.total, summary.currency)}")

    lines.append(f"Доходы: {format_money(summary.income_total, summary.currency)}")
    for item in sorted(summary.incomes, key=lambda c: c.total, reverse=True):
        lines.append(f"  {html.escape(item.name)}: {format_money(item.total, summary.currency)}")

    return "\n".join(lines)


def render_transaction_card(
    kind: TransactionKind,
    amount: Decimal,
    currency_code: str,
    account_name: str,
    category_name: str | None,
    occurred_on: date,
    comment: str | None,
    warnings: Sequence[str],
) -> str:
    """Текст карточки подтверждения из раздела 6.5 на готовых значениях."""
    verb = "Доход" if kind is TransactionKind.INCOME else "Расход"
    lines = [
        f"{verb}: {format_money(amount, currency_code)}",
        f"Счёт: {html.escape(account_name)}",
    ]
    if category_name is not None:
        lines.append(f"Категория: {html.escape(category_name)}")
    lines.append(f"Дата: {format_date(occurred_on)}")
    if comment is not None:
        lines.append(f"Комментарий: {html.escape(comment)}")
    for warning in warnings:
        lines.append(f"⚠ {warning}")
    return "\n".join(lines)


def render_undo(result: UndoResultDTO) -> str:
    """Подтверждение сторно с суммой и датой исходной операции."""
    original = result.original
    amount_text = format_money(original.amount, original.currency)
    date_text = format_date(original.occurred_on)
    return f"Операция отменена: {amount_text} от {date_text}"
