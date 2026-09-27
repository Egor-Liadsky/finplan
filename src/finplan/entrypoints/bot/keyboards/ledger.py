"""Клавиатуры диалогов расхода и дохода, общие для обоих сценариев.

`docs/architecture.md`, раздел 6.7: формат `callback_data` —
`<scope>:<action>:<id>:<page>`, не длиннее 64 байт; списки счетов и
категорий — по 8 элементов в сетке 2×4 с навигацией «‹ Назад · N/M ·
Вперёд ›» при числе страниц больше одной. Раздел 6.3, «Шаги диалога и
состояния FSM»: категория с потомками открывает свой уровень — дочерние
категории, кнопка выбора самой родительской категории целиком и «‹ Назад»
к верхнему уровню.

`ExpenseCallback` и `IncomeCallback` — фабрики `callback_data` роутеров
`expense` и `income` (раздел 6.2); переехали сюда из `keyboards/menu.py`,
который импортирует их отсюда для кнопок `exp:new` и `inc:new`.

Клавиатуры принимают фабрику `callback_data` параметром, поэтому один и
тот же код рисует и диалог расхода, и диалог дохода (подзадача 13b).
"""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from typing import Protocol

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from finplan.application.dto.accounts import AccountDTO
from finplan.application.dto.categories import CategoryDTO
from finplan.entrypoints.bot.keyboards.ids import short_id


class LedgerCallbackFactory(Protocol):
    """Конструктор `callback_data` вида `<scope>:<action>:<id>:<page>`.

    `ExpenseCallback` и `IncomeCallback` соответствуют этому протоколу
    структурно — вызов класса как конструктора создаёт экземпляр с этими
    тремя полями (раздел 6.7). Клавиатуры и шаги диалога типизируют фабрику
    этим протоколом, а не конкретным классом, поэтому не привязаны к виду
    операции.
    """

    def __call__(self, *, action: str, id: str = "", page: int = 0) -> CallbackData: ...


class ExpenseCallback(CallbackData, prefix="exp"):
    """`exp:<action>:<id>:<page>` — кнопки диалога расхода, раздел 6.7."""

    action: str
    id: str = ""
    page: int = 0


class IncomeCallback(CallbackData, prefix="inc"):
    """`inc:<action>:<id>:<page>` — кнопки диалога дохода, раздел 6.7."""

    action: str
    id: str = ""
    page: int = 0


_PAGE_SIZE = 8
_GRID_COLUMNS = 2
_BACK_TEXT = "‹ Назад"
_NEXT_TEXT = "Вперёд ›"


def _paginate[T](items: Sequence[T], page: int) -> tuple[Sequence[T], int, int]:
    """Возвращает элементы страницы, саму страницу и число страниц.

    Страница вне диапазона обрезается до последней валидной — так
    перерисовка устаревшей кнопки не падает на пустой странице.
    """
    total_pages = max(1, ceil(len(items) / _PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * _PAGE_SIZE
    return items[start : start + _PAGE_SIZE], page, total_pages


def _pagination_row(
    callback: LedgerCallbackFactory, *, page: int, total_pages: int, action: str
) -> tuple[InlineKeyboardButton, ...]:
    """«‹ Назад · N/M · Вперёд ›»: соседние страницы по кругу."""
    prev_page = (page - 1) % total_pages
    next_page = (page + 1) % total_pages
    return (
        InlineKeyboardButton(
            text=_BACK_TEXT, callback_data=callback(action=action, page=prev_page).pack()
        ),
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data=callback(action="noop", page=page).pack(),
        ),
        InlineKeyboardButton(
            text=_NEXT_TEXT, callback_data=callback(action=action, page=next_page).pack()
        ),
    )


def category_keyboard(
    items: Sequence[CategoryDTO],
    *,
    callback: LedgerCallbackFactory,
    page: int,
    parent: CategoryDTO | None,
) -> InlineKeyboardMarkup:
    """Категории текущего уровня.

    `items` — уже отфильтрованный список текущего уровня: корневые
    категории, если `parent is None`, иначе дети `parent`. При `parent`,
    заданном — под сеткой кнопка выбора `parent` целиком и «‹ Назад» к
    корню (раздел 6.3).
    """
    page_items, page, total_pages = _paginate(items, page)
    builder = InlineKeyboardBuilder()
    for category in page_items:
        builder.button(
            text=category.name,
            callback_data=callback(action="cat", id=short_id(category.id), page=page),
        )
    builder.adjust(_GRID_COLUMNS)
    if parent is not None:
        builder.row(
            InlineKeyboardButton(
                text=f"Выбрать «{parent.name}» целиком",
                callback_data=callback(action="cat_pick", id=short_id(parent.id)).pack(),
            )
        )
        builder.row(
            InlineKeyboardButton(text=_BACK_TEXT, callback_data=callback(action="cat_back").pack())
        )
    if total_pages > 1:
        nav = _pagination_row(callback, page=page, total_pages=total_pages, action="cat_page")
        builder.row(*nav)
    return builder.as_markup()


def account_keyboard(
    items: Sequence[AccountDTO], *, callback: LedgerCallbackFactory, page: int
) -> InlineKeyboardMarkup:
    """Неархивные счета пользователя, та же сетка и пагинация, без уровней."""
    page_items, page, total_pages = _paginate(items, page)
    builder = InlineKeyboardBuilder()
    for account in page_items:
        builder.button(
            text=account.name,
            callback_data=callback(action="acc", id=short_id(account.id), page=page),
        )
    builder.adjust(_GRID_COLUMNS)
    if total_pages > 1:
        nav = _pagination_row(callback, page=page, total_pages=total_pages, action="acc_page")
        builder.row(*nav)
    return builder.as_markup()


def confirm_keyboard(*, callback: LedgerCallbackFactory) -> InlineKeyboardMarkup:
    """«Сохранить», «Комментарий», «Отмена» — без кнопки «Дата», раздел 6.3."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Сохранить", callback_data=callback(action="save"))
    builder.button(text="Комментарий", callback_data=callback(action="comment"))
    builder.button(text="Отмена", callback_data=callback(action="cancel"))
    builder.adjust(1, 2)
    return builder.as_markup()
