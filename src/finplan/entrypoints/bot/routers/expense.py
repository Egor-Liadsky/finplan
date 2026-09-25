"""Роутер диалога добавления расхода.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `Command('expense')`,
`F.data.startswith('exp:')`, `StateFilter(AddExpense)`. Раздел 6.3, диаграмма
диалога расхода и абзацы после неё («Шаги диалога и состояния FSM»,
«Диалог дохода», «Что из диаграммы откладывается на этапе 1»). Раздел 6.7
(клавиатуры, короткие идентификаторы, идемпотентность нажатий) и раздел 12.3
(`external_key = 'bot:' || sha256(user_id, chat_id, message_id, payload)[:32]`).

Шаги диалога — функции `routers/ledger_dialog.py`, параметризованные
`DialogScope` (вид операции, группа состояний FSM, фабрика `callback_data`).
Этот модуль собирает `EXPENSE_SCOPE` из `AddExpense`/`ExpenseCallback` и
регистрирует хендлеры со своими фильтрами; `routers/income.py` собирает
`INCOME_SCOPE` из тех же функций `ledger_dialog.py`, ничего не копируя.

Тексты подсказок шагов и короткие сообщения отмены/сохранения документ не
задаёт дословно — решения исполнителя, перечислены в результате задачи 13a.
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
from finplan.entrypoints.bot.keyboards.ledger import ExpenseCallback
from finplan.entrypoints.bot.routers.ledger_dialog import (
    DialogScope,
    enter_dialog,
    handle_account_action,
    handle_amount,
    handle_category_action,
    handle_comment,
    handle_confirm_action,
)
from finplan.entrypoints.bot.states import AddExpense

router = Router(name="expense")

EXPENSE_SCOPE = DialogScope(
    kind=TransactionKind.EXPENSE,
    category_kind=CategoryKind.EXPENSE,
    states=AddExpense,
    callback=ExpenseCallback,
)


@router.message(Command("expense"))
async def handle_expense_command(message: Message, state: FSMContext) -> None:
    """`/expense` сбрасывает текущее состояние и открывает диалог расхода."""
    await enter_dialog(message, state, EXPENSE_SCOPE, edit=False)


@router.callback_query(ExpenseCallback.filter(F.action == "new"))
async def handle_expense_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка `exp:new` из меню «Добавить»."""
    await callback.answer()
    if isinstance(callback.message, Message):
        await enter_dialog(callback.message, state, EXPENSE_SCOPE, edit=True)


@router.message(StateFilter(AddExpense.amount), F.text & ~F.text.startswith("/"))
async def handle_expense_amount(
    message: Message, state: FSMContext, container: Container, user: UserDTO
) -> None:
    await handle_amount(message, state, container, user, EXPENSE_SCOPE)


@router.callback_query(ExpenseCallback.filter(), StateFilter(AddExpense.category))
async def handle_expense_category(
    callback: CallbackQuery,
    callback_data: ExpenseCallback,
    state: FSMContext,
    container: Container,
    user: UserDTO,
) -> None:
    await handle_category_action(callback, callback_data, state, container, user, EXPENSE_SCOPE)


@router.callback_query(ExpenseCallback.filter(), StateFilter(AddExpense.account))
async def handle_expense_account(
    callback: CallbackQuery,
    callback_data: ExpenseCallback,
    state: FSMContext,
    container: Container,
    user: UserDTO,
) -> None:
    await handle_account_action(callback, callback_data, state, container, user, EXPENSE_SCOPE)


@router.message(StateFilter(AddExpense.comment), F.text & ~F.text.startswith("/"))
async def handle_expense_comment(
    message: Message, state: FSMContext, container: Container, user: UserDTO
) -> None:
    await handle_comment(message, state, container, user, EXPENSE_SCOPE)


@router.callback_query(ExpenseCallback.filter(), StateFilter(AddExpense.confirm))
async def handle_expense_confirm(
    callback: CallbackQuery,
    callback_data: ExpenseCallback,
    state: FSMContext,
    container: Container,
    user: UserDTO,
) -> None:
    await handle_confirm_action(callback, callback_data, state, container, user, EXPENSE_SCOPE)
