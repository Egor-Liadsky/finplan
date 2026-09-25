"""Фабрика клиента Bot API.

`docs/architecture.md`, раздел 6.6, абзац о разметке сообщений: бот
отправляет сообщения с `parse_mode=HTML`, пользовательский текст
экранируется в форматтерах. Здесь режим разметки задаётся один раз для всех
вызовов, чтобы хендлеры его не повторяли.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from finplan.config import TelegramSettings


def create_bot(settings: TelegramSettings) -> Bot:
    """Создаёт `Bot` с `parse_mode=HTML` по умолчанию; к сети не обращается."""
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
