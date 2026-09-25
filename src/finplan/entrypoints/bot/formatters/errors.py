"""Тексты ошибок и предупреждений бота.

`docs/architecture.md`, раздел 6.6, последний абзац: словарь в этом модуле —
единственное место, где лежат тексты ошибок и предупреждений для
пользователя. Парсер и хендлеры возвращают код, а не фразу.
"""

from __future__ import annotations

from enum import StrEnum

from finplan.application.errors import InvalidCommandError, NotFoundError
from finplan.application.ports.repositories import DuplicateError
from finplan.domain.common.errors import (
    AlreadyReversedError,
    CurrencyMismatchError,
    InvariantViolationError,
)
from finplan.entrypoints.bot.parsers.quickinput import QuickInputError, QuickInputErrorCode

_DEFAULT_MESSAGE = "Что-то пошло не так, попробуйте ещё раз"

#: Раздел 6.6, таблица: формулировки, где строка в таблице есть, взяты
#: дословно; для остальных кодов — текст, объясняющий, что не так в строке.
_QUICK_INPUT_MESSAGES: dict[QuickInputErrorCode, str] = {
    QuickInputErrorCode.INVALID_AMOUNT: "Не понял сумму. Пример: -1200 кофе",
    QuickInputErrorCode.AMOUNT_OUT_OF_RANGE: "Сумма должна быть больше нуля и меньше триллиона",
    QuickInputErrorCode.EMPTY_MARKER: "После #, @ или ! должен идти текст",
    QuickInputErrorCode.DUPLICATE_MARKER: "Маркер #, @ или ! указан дважды",
    QuickInputErrorCode.INVALID_DATE: "Не понял дату. Пример: !14.03 или !вчера",
}

#: Раздел 2.2, абзац «Нарушение уникального ключа...»: повтор `external_key`
#: доходит до бота как «Уже сохранено».
_EXCEPTION_MESSAGES: dict[type[Exception], str] = {
    CurrencyMismatchError: "Валюты операции не совпадают",
    InvariantViolationError: "Операция нарушает правило учёта",
    AlreadyReversedError: "Эта операция уже отменена",
    NotFoundError: "Счёт или категория не найдены",
    InvalidCommandError: "Действие противоречит данным операции",
    DuplicateError: "Уже сохранено",
}


class BotWarning(StrEnum):
    """Коды предупреждений, показываемых в карточке операции.

    `COMMENT_TRUNCATED` совпадает по значению с
    `QuickInputWarning.COMMENT_TRUNCATED`. `AMOUNT_ROUNDED` передаёт хендлер
    подзадачи 14 после округления суммы до `minor_unit` валюты счёта.
    """

    COMMENT_TRUNCATED = "comment_truncated"
    AMOUNT_ROUNDED = "amount_rounded"


_WARNING_MESSAGES: dict[BotWarning, str] = {
    BotWarning.COMMENT_TRUNCATED: "Комментарий длиннее 500 символов, лишнее обрезано",
    BotWarning.AMOUNT_ROUNDED: "Сумма округлена до минимальной единицы валюты",
}


def error_message(exc: Exception) -> str:
    """Текст ошибки для пользователя по типу исключения с учётом MRO.

    Для `QuickInputError` текст выбирается по коду. Если записи нет,
    возвращается общий текст «Что-то пошло не так, попробуйте ещё раз».
    """
    if isinstance(exc, QuickInputError):
        return _QUICK_INPUT_MESSAGES.get(exc.code, _DEFAULT_MESSAGE)
    for cls in type(exc).__mro__:
        message = _EXCEPTION_MESSAGES.get(cls)
        if message is not None:
            return message
    return _DEFAULT_MESSAGE


def warning_message(code: str) -> str:
    """Текст предупреждения по коду `BotWarning`."""
    return _WARNING_MESSAGES[BotWarning(code)]


class BotInputError(StrEnum):
    """Коды ошибок ввода, которые парсер строки не покрывает.

    `UNKNOWN_TIMEZONE` — шаг `Onboarding.timezone` (раздел 6.3): имя IANA,
    присланное текстом, не найдено в `zoneinfo.available_timezones()`.
    """

    UNKNOWN_TIMEZONE = "unknown_timezone"


_INPUT_ERROR_MESSAGES: dict[BotInputError, str] = {
    BotInputError.UNKNOWN_TIMEZONE: "Не знаю такую таймзону. Пример: Europe/Moscow",
}


def input_error_message(code: BotInputError) -> str:
    """Текст ошибки ввода по коду `BotInputError`."""
    return _INPUT_ERROR_MESSAGES[code]
