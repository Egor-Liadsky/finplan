"""Роутер `fallback` — всё, что не поймали другие роутеры.

`docs/architecture.md`, раздел 6.2, таблица роутеров, строка `fallback.router`:
сообщение — подсказка «не понял, /help»; нажатие кнопки без обработчика —
`answer_callback_query` с текстом «Кнопка устарела», чтобы у клиента не
висели часики. Регистрируется последним внутри `registered` (раздел 6.2,
абзац «Регистрация»).

Точные тексты подсказок документ не задаёт — решения исполнителя,
перечислены в результате задачи.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message

router = Router(name="fallback")

_UNKNOWN_MESSAGE_TEXT = "Не понял. Наберите /help — там команды и синтаксис быстрого ввода."
_STALE_BUTTON_TEXT = "Кнопка устарела"


@router.message()
async def handle_unknown_message(message: Message) -> None:
    """Отвечает подсказкой на сообщение, не пойманное ни одним роутером выше."""
    await message.answer(_UNKNOWN_MESSAGE_TEXT)


@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery) -> None:
    """Закрывает «часики» кнопки без обработчика текстом «Кнопка устарела»."""
    await callback.answer(_STALE_BUTTON_TEXT)
