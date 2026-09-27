"""Главное меню этапа 1: клавиатуры `nav:*` и постоянная reply-клавиатура.

`docs/architecture.md`, раздел 6.7: на этапе 1 в главном меню три пункта —
«Добавить» с «Расход» и «Доход», «Счета» с «Остатки по счетам», «Отчёты» с
«Сегодня» и «Этот месяц». Переходы между уровнями меню — `nav:<пункт>`
(`nav:menu`, `nav:add`, `nav:acc`, `nav:rep`), конечные кнопки — префиксы
роутеров, которые их обрабатывают (`exp:new`, `inc:new`, `acc:balance`,
`rep:today`, `rep:month`); `accounts.router` и `reports.router` пока пустые
(подзадача 14) — `CallbackData`-классы для их кнопок временно определены
здесь же, рядом с клавиатурой, которая их рисует.

Кнопка «‹ Назад» в подменю и подписи пунктов меню документ не задаёт
дословно — это решения исполнителя, см. результат задачи.

`ExpenseCallback` и `IncomeCallback` переехали в `keyboards/ledger.py`
(подзадача 13a): диалоги расхода и дохода используют их же поля `action`,
`id`, `page`, а не только `action`, которого было довольно для одной
кнопки `exp:new` / `inc:new`.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from finplan.entrypoints.bot.keyboards.ledger import ExpenseCallback, IncomeCallback

__all__ = [
    "REPLY_ADD_TEXT",
    "REPLY_MENU_TEXT",
    "AccountsCallback",
    "ExpenseCallback",
    "IncomeCallback",
    "NavCallback",
    "ReportsCallback",
    "accounts_menu_keyboard",
    "add_menu_keyboard",
    "main_menu_keyboard",
    "reply_keyboard",
    "reports_menu_keyboard",
]


class NavCallback(CallbackData, prefix="nav"):
    """`nav:<target>` — переход между уровнями меню, раздел 6.7."""

    target: str


class AccountsCallback(CallbackData, prefix="acc"):
    """`acc:<action>` — кнопки роутера `accounts` (подзадача 14)."""

    action: str


class ReportsCallback(CallbackData, prefix="rep"):
    """`rep:<action>` — кнопки роутера `reports` (подзадача 14)."""

    action: str


_BACK_TEXT = "‹ Назад"

#: Раздел 6.7, reply-клавиатура: тексты кнопок скопированы дословно.
REPLY_ADD_TEXT = "➕ Операция"
REPLY_MENU_TEXT = "📊 Меню"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Корень главного меню: три доступных на этапе 1 пункта."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить", callback_data=NavCallback(target="add"))
    builder.button(text="Счета", callback_data=NavCallback(target="acc"))
    builder.button(text="Отчёты", callback_data=NavCallback(target="rep"))
    builder.adjust(1)
    return builder.as_markup()


def add_menu_keyboard() -> InlineKeyboardMarkup:
    """Подменю «Добавить»: «Расход» и «Доход»."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Расход", callback_data=ExpenseCallback(action="new"))
    builder.button(text="Доход", callback_data=IncomeCallback(action="new"))
    builder.button(text=_BACK_TEXT, callback_data=NavCallback(target="menu"))
    builder.adjust(2, 1)
    return builder.as_markup()


def accounts_menu_keyboard() -> InlineKeyboardMarkup:
    """Подменю «Счета»: «Остатки по счетам»."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Остатки по счетам", callback_data=AccountsCallback(action="balance"))
    builder.button(text=_BACK_TEXT, callback_data=NavCallback(target="menu"))
    builder.adjust(1)
    return builder.as_markup()


def reports_menu_keyboard() -> InlineKeyboardMarkup:
    """Подменю «Отчёты»: «Сегодня» и «Этот месяц»."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Сегодня", callback_data=ReportsCallback(action="today"))
    builder.button(text="Этот месяц", callback_data=ReportsCallback(action="month"))
    builder.button(text=_BACK_TEXT, callback_data=NavCallback(target="menu"))
    builder.adjust(2, 1)
    return builder.as_markup()


def reply_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная reply-клавиатура из двух кнопок, раздел 6.7."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=REPLY_ADD_TEXT), KeyboardButton(text=REPLY_MENU_TEXT))
    return builder.as_markup(resize_keyboard=True)
