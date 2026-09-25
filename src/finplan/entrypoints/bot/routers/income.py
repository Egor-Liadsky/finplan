"""Роутер диалога добавления дохода.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `Command('income')`,
`F.data.startswith('inc:')`, `StateFilter(AddIncome)`. Раздел 6.3, «Диалог
дохода»: тот же диалог, что и диалог расхода, с категориями вида `income`,
включая шаг комментария; шаг `recurring` не используется — раздел 6.3, «Что
из диаграммы откладывается на этапе 1».

Шаги диалога — функции `routers/ledger_dialog.py`, параметризованные
`DialogScope`. Этот модуль собирает `INCOME_SCOPE` из `AddIncome`/
`IncomeCallback` и регистрирует хендлеры со своими фильтрами, ничего не
копируя из `routers/expense.py`.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from finplan.application.dto.auth import UserDTO
from finplan.container import Container
from finplan.domain.entities.category import CategoryKind
from finplan.domain.entities.transaction import TransactionKind
from finplan.entrypoints.bot.keyboards.ledger import IncomeCallback
from finplan.entrypoints.bot.routers.ledger_dialog import (
    DialogScope,
    enter_dialog,
    handle_account_action,
    handle_amount,
    handle_category_action,
    handle_comment,
    handle_confirm_action,
)
from finplan.entrypoints.bot.states import AddIncome

router = Router(name="income")

INCOME_SCOPE = DialogScope(
    kind=TransactionKind.INCOME,
    category_kind=CategoryKind.INCOME,
    states=AddIncome,
    callback=IncomeCallback,
)


@router.message(Command("income"))
async def handle_income_command(message: Message, state: FSMContext) -> None:
    """`/income` сбрасывает текущее состояние и открывает диалог дохода."""
    await enter_dialog(message, state, INCOME_SCOPE, edit=False)


@router.callback_query(IncomeCallback.filter(F.action == "new"))
async def handle_income_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка `inc:new` из меню «Добавить»."""
    await callback.answer()
    if isinstance(callback.message, Message):
        await enter_dialog(callback.message, state, INCOME_SCOPE, edit=True)


@router.message(StateFilter(AddIncome.amount), F.text & ~F.text.startswith("/"))
async def handle_income_amount(
    message: Message, state: FSMContext, container: Container, user: UserDTO
) -> None:
    await handle_amount(message, state, container, user, INCOME_SCOPE)


@router.callback_query(IncomeCallback.filter(), StateFilter(AddIncome.category))
async def handle_income_category(
    callback: CallbackQuery,
    callback_data: IncomeCallback,
    state: FSMContext,
    container: Container,
    user: UserDTO,
) -> None:
    await handle_category_action(callback, callback_data, state, container, user, INCOME_SCOPE)


@router.callback_query(IncomeCallback.filter(), StateFilter(AddIncome.account))
async def handle_income_account(
    callback: CallbackQuery,
    callback_data: IncomeCallback,
    state: FSMContext,
    container: Container,
    user: UserDTO,
) -> None:
    await handle_account_action(callback, callback_data, state, container, user, INCOME_SCOPE)


@router.message(StateFilter(AddIncome.comment), F.text & ~F.text.startswith("/"))
async def handle_income_comment(
    message: Message, state: FSMContext, container: Container, user: UserDTO
) -> None:
    await handle_comment(message, state, container, user, INCOME_SCOPE)


@router.callback_query(IncomeCallback.filter(), StateFilter(AddIncome.confirm))
async def handle_income_confirm(
    callback: CallbackQuery,
    callback_data: IncomeCallback,
    state: FSMContext,
    container: Container,
    user: UserDTO,
) -> None:
    await handle_confirm_action(callback, callback_data, state, container, user, INCOME_SCOPE)
