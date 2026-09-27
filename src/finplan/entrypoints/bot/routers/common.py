"""Роутер `common`: `/cancel`, `/menu`, `nav:*`, кнопки reply-клавиатуры.

`docs/architecture.md`, раздел 6.2, таблица роутеров, строка `common.router`:
`Command('cancel')`, `Command('menu')`, `F.data.startswith('nav:')`, тексты
кнопок reply-клавиатуры. Раздел 6.7: главное меню перерисовывается
редактированием того же сообщения (`edit_message_text`) на нажатие кнопки и
отправляется новым сообщением на команду или текст reply-клавиатуры.

Заголовки экранов меню и тексты ответов `/cancel` документ не задаёт
дословно — решения исполнителя, перечислены в результате задачи.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from finplan.entrypoints.bot.keyboards.menu import (
    REPLY_ADD_TEXT,
    REPLY_MENU_TEXT,
    NavCallback,
    accounts_menu_keyboard,
    add_menu_keyboard,
    main_menu_keyboard,
    reports_menu_keyboard,
)

router = Router(name="common")

_CANCELLED_TEXT = "Диалог отменён"
_NOTHING_TO_CANCEL_TEXT = "Отменять нечего"

#: Заголовок и клавиатура каждого экрана меню по `nav:<target>`.
_NAV_SCREENS: dict[str, tuple[str, InlineKeyboardMarkup]] = {
    "menu": ("Главное меню", main_menu_keyboard()),
    "add": ("Добавить", add_menu_keyboard()),
    "acc": ("Счета", accounts_menu_keyboard()),
    "rep": ("Отчёты", reports_menu_keyboard()),
}


@router.message(Command("cancel"))
async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Сбрасывает состояние FSM и сообщает, было ли что отменять."""
    current_state = await state.get_state()
    await state.clear()
    text = _NOTHING_TO_CANCEL_TEXT if current_state is None else _CANCELLED_TEXT
    await message.answer(text)


@router.message(Command("menu"))
async def handle_menu_command(message: Message) -> None:
    """Отправляет главное меню новым сообщением."""
    title, keyboard = _NAV_SCREENS["menu"]
    await message.answer(title, reply_markup=keyboard)


@router.message(F.text == REPLY_MENU_TEXT)
async def handle_menu_button(message: Message) -> None:
    """Кнопка «📊 Меню» reply-клавиатуры — то же самое, что `/menu`."""
    title, keyboard = _NAV_SCREENS["menu"]
    await message.answer(title, reply_markup=keyboard)


@router.message(F.text == REPLY_ADD_TEXT)
async def handle_add_button(message: Message) -> None:
    """Кнопка «➕ Операция» reply-клавиатуры открывает подменю «Добавить»."""
    title, keyboard = _NAV_SCREENS["add"]
    await message.answer(title, reply_markup=keyboard)


@router.callback_query(NavCallback.filter())
async def handle_nav(callback: CallbackQuery, callback_data: NavCallback) -> None:
    """Перерисовывает главное меню и подменю редактированием сообщения."""
    await callback.answer()
    screen = _NAV_SCREENS.get(callback_data.target)
    if screen is None or not isinstance(callback.message, Message):
        return
    title, keyboard = screen
    await callback.message.edit_text(title, reply_markup=keyboard)
