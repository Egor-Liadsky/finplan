"""Клавиатуры онбординга: валюта, таймзона, тип счёта, «Начать с нуля».

`docs/architecture.md`, раздел 6.3, абзац «Онбординг», и раздел 6.7,
«Соглашение по `callback_data`»: префикс `onb:`, формат
`<scope>:<action>:<id>`, обрабатывается `start.router`.

Тексты кнопок таймзон придуманы исполнителем: раздел 6.3 называет только
имена IANA и требование «город и смещение», без готовых подписей.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from finplan.domain.entities.account import AccountType


class OnboardingCallback(CallbackData, prefix="onb"):
    """`onb:<step>:<value>` — один шаг онбординга, раздел 6.3."""

    step: str
    value: str


#: Раздел 3.1: справочник валют онбординга — RUB, USD, EUR.
_CURRENCIES: tuple[str, ...] = ("RUB", "USD", "EUR")

#: Раздел 6.3, шаг `timezone`: одиннадцать поясов России от UTC+2 до
#: UTC+12, имя IANA и подпись «город (смещение)» на кнопке.
_TIMEZONES: tuple[tuple[str, str], ...] = (
    ("Europe/Kaliningrad", "Калининград (UTC+2)"),
    ("Europe/Moscow", "Москва (UTC+3)"),
    ("Europe/Samara", "Самара (UTC+4)"),
    ("Asia/Yekaterinburg", "Екатеринбург (UTC+5)"),
    ("Asia/Omsk", "Омск (UTC+6)"),
    ("Asia/Krasnoyarsk", "Красноярск (UTC+7)"),
    ("Asia/Irkutsk", "Иркутск (UTC+8)"),
    ("Asia/Yakutsk", "Якутск (UTC+9)"),
    ("Asia/Vladivostok", "Владивосток (UTC+10)"),
    ("Asia/Magadan", "Магадан (UTC+11)"),
    ("Asia/Kamchatka", "Камчатка (UTC+12)"),
)

#: Раздел 6.3, шаг `account_type`: подписи кнопок даны в самом документе.
_ACCOUNT_TYPES: tuple[tuple[AccountType, str], ...] = (
    (AccountType.CASH, "Наличные"),
    (AccountType.CARD, "Карта"),
    (AccountType.BANK_ACCOUNT, "Счёт в банке"),
)

#: Публичная проекция `_ACCOUNT_TYPES`: подпись кнопки становится именем
#: первого счёта (раздел 6.3, шаг `account_type`, последний абзац). Нужна
#: `start.router` при вызове `RegisterUserCommand`.
ACCOUNT_TYPE_LABELS: dict[AccountType, str] = dict(_ACCOUNT_TYPES)

_START_FROM_ZERO_TEXT = "Начать с нуля"


def base_currency_keyboard() -> InlineKeyboardMarkup:
    """Кнопки шага 1 онбординга: базовая валюта."""
    builder = InlineKeyboardBuilder()
    for code in _CURRENCIES:
        builder.button(text=code, callback_data=OnboardingCallback(step="currency", value=code))
    builder.adjust(3)
    return builder.as_markup()


def timezone_keyboard() -> InlineKeyboardMarkup:
    """Кнопки шага 2 онбординга: одиннадцать таймзон России."""
    builder = InlineKeyboardBuilder()
    for iana_name, label in _TIMEZONES:
        builder.button(
            text=label, callback_data=OnboardingCallback(step="timezone", value=iana_name)
        )
    builder.adjust(2)
    return builder.as_markup()


def account_type_keyboard() -> InlineKeyboardMarkup:
    """Кнопки шага 3 онбординга: тип первого счёта."""
    builder = InlineKeyboardBuilder()
    for account_type, label in _ACCOUNT_TYPES:
        builder.button(
            text=label,
            callback_data=OnboardingCallback(step="account_type", value=account_type.value),
        )
    builder.adjust(1)
    return builder.as_markup()


def opening_balance_keyboard() -> InlineKeyboardMarkup:
    """Кнопка шага 4 онбординга: «Начать с нуля»."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_START_FROM_ZERO_TEXT,
        callback_data=OnboardingCallback(step="opening_balance", value="zero"),
    )
    return builder.as_markup()
