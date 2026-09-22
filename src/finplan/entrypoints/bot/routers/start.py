"""Хендлер команды `/start` — заглушка этапа 0.

Раздел `docs/architecture.md`, 13 «Этап 0»: пустой бот, отвечающий на
`/start`. Никаких обращений к базе и созданию пользователя — это предмет
этапа 1 (раздел 6.1).
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")

_WELCOME_TEXT = (
    "Бот finplan запущен. Учёт расходов и доходов появится в одном из следующих обновлений."
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Отвечает коротким текстом о том, что бот запущен."""
    await message.answer(_WELCOME_TEXT)
