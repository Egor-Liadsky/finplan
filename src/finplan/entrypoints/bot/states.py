"""Классы `StatesGroup` для диалогов бота этапа 1.

`docs/architecture.md`, раздел 6.3: код групп состояний скопирован дословно.
Группы других этапов (`AddTransfer`, `AddValuation`, `AddGoal`, `AddDeposit`)
появятся вместе со своими этапами и здесь не заводятся.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddExpense(StatesGroup):
    amount = State()
    category = State()
    account = State()
    comment = State()
    confirm = State()


class AddIncome(StatesGroup):
    amount = State()
    category = State()
    account = State()
    recurring = State()  # предложить сделать регулярным
    confirm = State()


class QuickConfirm(StatesGroup):
    resolve_category = State()  # быстрый ввод не распознал категорию
    resolve_account = State()


class Onboarding(StatesGroup):
    base_currency = State()
    timezone = State()
    account_type = State()
    opening_balance = State()
