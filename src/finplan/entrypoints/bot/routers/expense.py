"""Роутер диалога добавления расхода и общая логика шагов расхода/дохода.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `Command('expense')`,
`F.data.startswith('exp:')`, `StateFilter(AddExpense)`. Раздел 6.3, диаграмма
диалога расхода и абзацы после неё («Шаги диалога и состояния FSM»,
«Диалог дохода», «Что из диаграммы откладывается на этапе 1»). Раздел 6.7
(клавиатуры, короткие идентификаторы, идемпотентность нажатий) и раздел 12.3
(`external_key = 'bot:' || sha256(user_id, chat_id, message_id, payload)[:32]`).

Шаги диалога — функции `_show_*`/`_handle_*`, параметризованные `DialogScope`
(вид операции, группа состояний FSM, фабрика `callback_data`). Подзадача 13b
подключает `routers/income.py` к этим же функциям с `INCOME_SCOPE`, не
копируя их: `AddIncome` повторяет диалог расхода с категориями `income`
(раздел 6.3, «Диалог дохода»).

Тексты подсказок шагов и короткие сообщения отмены/сохранения документ не
задаёт дословно — решения исполнителя, перечислены в результате задачи.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from finplan.application.dto.accounts import AccountDTO, ListAccountsQuery
from finplan.application.dto.auth import UserDTO
from finplan.application.dto.categories import CategoryDTO, ListCategoriesQuery
from finplan.application.dto.transactions import RecordTransactionCommand
from finplan.container import Container
from finplan.domain.common.currency import EUR, RUB, USD, Currency
from finplan.domain.common.money import Money
from finplan.domain.entities.category import CategoryKind
from finplan.domain.entities.transaction import TransactionKind
from finplan.entrypoints.bot.formatters.errors import BotWarning, warning_message
from finplan.entrypoints.bot.formatters.money import format_money
from finplan.entrypoints.bot.formatters.reports import render_transaction_card
from finplan.entrypoints.bot.keyboards.ids import resolve_short_id
from finplan.entrypoints.bot.keyboards.ledger import (
    ExpenseCallback,
    LedgerCallbackFactory,
    account_keyboard,
    category_keyboard,
    confirm_keyboard,
)
from finplan.entrypoints.bot.parsers.quickinput import parse_amount
from finplan.entrypoints.bot.states import AddExpense

router = Router(name="expense")

_CURRENCIES: dict[str, Currency] = {c.code: c for c in (RUB, USD, EUR)}

_STALE_BUTTON_TEXT = "Кнопка устарела"
_COMMENT_PROMPT_TEXT = "Пришлите комментарий (до 500 символов)."
_NO_ACCOUNTS_TEXT = "Нет доступных счетов."
_CHILD_CATEGORY_PROMPT_TEMPLATE = "Категория «{name}» — выберите подкатегорию или саму «{name}»."
_ACCOUNT_PROMPT_TEXT = "Счёт?"
_AMOUNT_PROMPT_TEXTS: dict[TransactionKind, str] = {
    TransactionKind.EXPENSE: "Сумма расхода? Пришлите число, например 1200 или 1200,50.",
    TransactionKind.INCOME: "Сумма дохода? Пришлите число, например 50000.",
}
_CANCELLED_TEXTS: dict[TransactionKind, str] = {
    TransactionKind.EXPENSE: "Расход отменён",
    TransactionKind.INCOME: "Доход отменён",
}
_CATEGORY_ROOT_PROMPTS: dict[TransactionKind, str] = {
    TransactionKind.EXPENSE: "Категория расхода?",
    TransactionKind.INCOME: "Категория дохода?",
}
_SAVED_TEXT_TEMPLATE = "Сохранено: {amount}"


class _LedgerCallbackData(Protocol):
    """Структурный протокол полей `callback_data` диалогов расхода/дохода."""

    action: str
    id: str
    page: int


class _DialogStates(Protocol):
    """Структурный протокол состояний `AddExpense`/`AddIncome`, раздел 6.3."""

    amount: State
    category: State
    account: State
    comment: State
    confirm: State


@dataclass(frozen=True, slots=True)
class DialogScope:
    """Параметры, различающие диалог расхода и диалог дохода.

    `docs/architecture.md`, раздел 6.3, «Диалог дохода»: тот же диалог с
    категориями вида `income` — вид операции, группа состояний и фабрика
    `callback_data` меняются, шаги — нет.
    """

    kind: TransactionKind
    category_kind: CategoryKind
    states: type[_DialogStates]
    callback: LedgerCallbackFactory


EXPENSE_SCOPE = DialogScope(
    kind=TransactionKind.EXPENSE,
    category_kind=CategoryKind.EXPENSE,
    states=AddExpense,
    callback=ExpenseCallback,
)


# --- Общие шаги, параметризованные `DialogScope` ---------------------------


async def _list_categories(
    container: Container, user: UserDTO, scope: DialogScope
) -> tuple[CategoryDTO, ...]:
    result = await container.list_categories(
        ListCategoriesQuery(user_id=user.id, kind=scope.category_kind)
    )
    return result.items


async def _list_accounts(container: Container, user: UserDTO) -> tuple[AccountDTO, ...]:
    result = await container.list_accounts(ListAccountsQuery(user_id=user.id))
    return result.items


async def enter_dialog(
    message: Message, state: FSMContext, scope: DialogScope, *, edit: bool
) -> None:
    """Сбрасывает состояние и переходит к шагу суммы (раздел 6.2, «Команды посреди диалога»)."""
    await state.clear()
    await state.set_state(scope.states.amount)
    text = _AMOUNT_PROMPT_TEXTS[scope.kind]
    if edit:
        await message.edit_text(text)
    else:
        await message.answer(text)


async def handle_amount(
    message: Message, state: FSMContext, container: Container, user: UserDTO, scope: DialogScope
) -> None:
    """Шаг суммы: `parse_amount`; ошибка разбора уходит в `ErrorMiddleware`, шаг повторяется."""
    amount = parse_amount(message.text or "")
    await state.update_data(amount=str(amount))
    await state.set_state(scope.states.category)
    await _show_category_step(
        message, state, container, user, scope, parent_id=None, page=0, edit=False
    )


async def _show_category_step(
    message: Message,
    state: FSMContext,
    container: Container,
    user: UserDTO,
    scope: DialogScope,
    *,
    parent_id: str | None,
    page: int,
    edit: bool,
) -> None:
    categories = await _list_categories(container, user, scope)
    parent: CategoryDTO | None = None
    if parent_id is not None:
        parent = next((c for c in categories if str(c.id) == parent_id), None)
    if parent is None:
        level_items = [c for c in categories if c.parent_id is None]
        text = _CATEGORY_ROOT_PROMPTS[scope.kind]
        await state.update_data(category_parent=None)
    else:
        level_items = [c for c in categories if c.parent_id == parent.id]
        text = _CHILD_CATEGORY_PROMPT_TEMPLATE.format(name=parent.name)
    keyboard = category_keyboard(level_items, callback=scope.callback, page=page, parent=parent)
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def handle_category_action(
    callback: CallbackQuery,
    callback_data: _LedgerCallbackData,
    state: FSMContext,
    container: Container,
    user: UserDTO,
    scope: DialogScope,
) -> None:
    """Диспетчер действий шага категории: выбор, уровень, пагинация, устаревание."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    action = callback_data.action

    if action == "noop":
        await callback.answer()
        return
    if action == "cat_back":
        await callback.answer()
        await _show_category_step(
            callback.message, state, container, user, scope, parent_id=None, page=0, edit=True
        )
        return
    if action == "cat_page":
        await callback.answer()
        data = await state.get_data()
        await _show_category_step(
            callback.message,
            state,
            container,
            user,
            scope,
            parent_id=data.get("category_parent"),
            page=callback_data.page,
            edit=True,
        )
        return

    categories = await _list_categories(container, user, scope)
    category = resolve_short_id(callback_data.id, categories)
    if category is None:
        await callback.answer(_STALE_BUTTON_TEXT)
        data = await state.get_data()
        await _show_category_step(
            callback.message,
            state,
            container,
            user,
            scope,
            parent_id=data.get("category_parent"),
            page=0,
            edit=True,
        )
        return

    await callback.answer()
    if action == "cat_pick":
        await _finalize_category(callback.message, category, state, container, user, scope)
        return
    has_children = any(c.parent_id == category.id for c in categories)
    if has_children:
        await state.update_data(category_parent=str(category.id))
        await _show_category_step(
            callback.message,
            state,
            container,
            user,
            scope,
            parent_id=str(category.id),
            page=0,
            edit=True,
        )
    else:
        await _finalize_category(callback.message, category, state, container, user, scope)


async def _finalize_category(
    message: Message,
    category: CategoryDTO,
    state: FSMContext,
    container: Container,
    user: UserDTO,
    scope: DialogScope,
) -> None:
    await state.update_data(category_id=str(category.id), category_parent=None)
    await state.set_state(scope.states.account)
    await _show_account_step(message, state, container, user, scope, page=0, edit=True)


async def _show_account_step(
    message: Message,
    state: FSMContext,
    container: Container,
    user: UserDTO,
    scope: DialogScope,
    *,
    page: int,
    edit: bool,
) -> None:
    accounts = await _list_accounts(container, user)
    if not accounts:
        if edit:
            await message.edit_text(_NO_ACCOUNTS_TEXT)
        else:
            await message.answer(_NO_ACCOUNTS_TEXT)
        return
    if len(accounts) == 1:
        await state.update_data(account_id=str(accounts[0].id))
        await state.set_state(scope.states.confirm)
        await _show_confirm_step(message, state, container, user, scope, edit=edit)
        return
    keyboard = account_keyboard(accounts, callback=scope.callback, page=page)
    if edit:
        await message.edit_text(_ACCOUNT_PROMPT_TEXT, reply_markup=keyboard)
    else:
        await message.answer(_ACCOUNT_PROMPT_TEXT, reply_markup=keyboard)


async def handle_account_action(
    callback: CallbackQuery,
    callback_data: _LedgerCallbackData,
    state: FSMContext,
    container: Container,
    user: UserDTO,
    scope: DialogScope,
) -> None:
    """Диспетчер действий шага счёта: выбор, пагинация, устаревание."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    action = callback_data.action

    if action == "noop":
        await callback.answer()
        return
    if action == "acc_page":
        await callback.answer()
        await _show_account_step(
            callback.message, state, container, user, scope, page=callback_data.page, edit=True
        )
        return

    accounts = await _list_accounts(container, user)
    account = resolve_short_id(callback_data.id, accounts)
    if account is None:
        await callback.answer(_STALE_BUTTON_TEXT)
        await _show_account_step(callback.message, state, container, user, scope, page=0, edit=True)
        return

    await callback.answer()
    await state.update_data(account_id=str(account.id))
    await state.set_state(scope.states.confirm)
    await _show_confirm_step(callback.message, state, container, user, scope, edit=True)


async def _show_confirm_step(
    message: Message,
    state: FSMContext,
    container: Container,
    user: UserDTO,
    scope: DialogScope,
    *,
    edit: bool,
) -> None:
    data = await state.get_data()
    amount = Decimal(data["amount"])
    accounts = await _list_accounts(container, user)
    account = next(a for a in accounts if str(a.id) == data["account_id"])
    categories = await _list_categories(container, user, scope)
    category = next((c for c in categories if str(c.id) == data.get("category_id")), None)
    comment = data.get("comment")

    warnings: list[str] = []
    display_amount = amount
    currency = _CURRENCIES.get(account.currency)
    if currency is not None:
        rounded = Money(amount, currency).round_to_minor_unit()
        if rounded.amount != amount:
            display_amount = rounded.amount
            warnings.append(warning_message(BotWarning.AMOUNT_ROUNDED.value))
    if data.get("comment_truncated"):
        warnings.append(warning_message(BotWarning.COMMENT_TRUNCATED.value))

    today = container.clock.now().astimezone(ZoneInfo(user.timezone)).date()
    text = render_transaction_card(
        kind=scope.kind,
        amount=display_amount,
        currency_code=account.currency,
        account_name=account.name,
        category_name=category.name if category is not None else None,
        occurred_on=today,
        comment=comment,
        warnings=warnings,
    )
    keyboard = confirm_keyboard(callback=scope.callback)
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def handle_comment(
    message: Message, state: FSMContext, container: Container, user: UserDTO, scope: DialogScope
) -> None:
    """Шаг комментария: обрезка до 500 символов с предупреждением, возврат к `confirm`."""
    text = (message.text or "").strip()
    truncated = False
    if len(text) > 500:
        text = text[:500]
        truncated = True
    await state.update_data(comment=text or None, comment_truncated=truncated)
    await state.set_state(scope.states.confirm)
    await _show_confirm_step(message, state, container, user, scope, edit=False)


async def handle_confirm_action(
    callback: CallbackQuery,
    callback_data: _LedgerCallbackData,
    state: FSMContext,
    container: Container,
    user: UserDTO,
    scope: DialogScope,
) -> None:
    """«Сохранить», «Комментарий», «Отмена» — `answer_callback_query` первым делом (раздел 12.3)."""
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    action = callback_data.action
    if action == "cancel":
        await state.clear()
        await callback.message.edit_text(_CANCELLED_TEXTS[scope.kind])
        return
    if action == "comment":
        await state.set_state(scope.states.comment)
        await callback.message.edit_text(_COMMENT_PROMPT_TEXT)
        return
    if action == "save":
        await _save_transaction(callback.message, state, container, user, scope)


def _external_key(user_id: UUID, chat_id: int, message_id: int, payload: dict[str, Any]) -> str:
    """`'bot:' || sha256(user_id, chat_id, message_id, payload)[:32]` (раздел 12.3)."""
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = sha256(f"{user_id}:{chat_id}:{message_id}:{serialized}".encode()).hexdigest()
    return f"bot:{digest[:32]}"


async def _save_transaction(
    message: Message, state: FSMContext, container: Container, user: UserDTO, scope: DialogScope
) -> None:
    """Записывает операцию; состояние очищается только после успеха (раздел 6.7).

    Повторное нажатие до успеха воспроизводит тот же `external_key`, и
    `RecordTransaction` отвечает `DuplicateError`, который `ErrorMiddleware`
    превращает в «Уже сохранено».
    """
    data = await state.get_data()
    payload = {
        "amount": data["amount"],
        "category_id": data.get("category_id"),
        "account_id": data.get("account_id"),
        "comment": data.get("comment"),
    }
    external_key = _external_key(user.id, message.chat.id, message.message_id, payload)
    command = RecordTransactionCommand(
        user_id=user.id,
        kind=scope.kind,
        amount=Decimal(data["amount"]),
        account_id=UUID(data["account_id"]),
        category_id=UUID(data["category_id"]) if data.get("category_id") else None,
        occurred_at=None,
        comment=data.get("comment"),
        external_key=external_key,
        source="bot",
    )
    result = await container.record_transaction(command)
    await state.clear()
    saved_amount = format_money(result.amount, result.currency)
    await message.edit_text(_SAVED_TEXT_TEMPLATE.format(amount=saved_amount))


# --- Роутер `expense`: регистрация с `AddExpense` и `ExpenseCallback` ------


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
