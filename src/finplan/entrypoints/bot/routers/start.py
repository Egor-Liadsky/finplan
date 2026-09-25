"""Роутер `start`: `/start`, `/help` и все шаги `Onboarding`.

`docs/architecture.md`, раздел 6.2, строка `start.router` (`CommandStart()`,
`Command('help')`) и абзац «Регистрация»: подключается к диспетчеру напрямую,
онбордингу пользователь из базы не нужен. Раздел 6.3, абзац «Онбординг»:
четыре шага FSM, ничего не пишется в базу до финального вызова
`RegisterUser`.

Тексты приглашений на каждом шаге, текст `/help` и подтверждение по
завершении онбординга документ не задаёт дословно — решения исполнителя,
перечислены в результате задачи. Пример из таблицы 6.5 скопирован дословно.

`/cancel` посреди онбординга обрабатывается здесь, а не в `common.router`:
пользователя в базе ещё нет, и `UserMiddleware` роутера `registered` его бы
не пропустил (раздел 6.2, строка `start.router`).
"""

from __future__ import annotations

from decimal import Decimal
from zoneinfo import available_timezones

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TelegramUser

from finplan.application.dto.auth import FindUserByTelegramIdQuery, RegisterUserCommand
from finplan.container import Container
from finplan.domain.entities.account import AccountType
from finplan.entrypoints.bot.formatters.errors import BotInputError, input_error_message
from finplan.entrypoints.bot.formatters.money import format_money
from finplan.entrypoints.bot.keyboards.menu import main_menu_keyboard, reply_keyboard
from finplan.entrypoints.bot.keyboards.onboarding import (
    ACCOUNT_TYPE_LABELS,
    OnboardingCallback,
    account_type_keyboard,
    base_currency_keyboard,
    opening_balance_keyboard,
    timezone_keyboard,
)
from finplan.entrypoints.bot.parsers.quickinput import parse_amount
from finplan.entrypoints.bot.states import Onboarding

router = Router(name="start")

_WELCOME_BACK_TEXT = "С возвращением! Открываю главное меню."
_ONBOARDING_INTRO_TEXT = (
    "Давайте настроим учёт. Сначала выберите базовую валюту — в ней будут считаться отчёты."
)
_TIMEZONE_PROMPT_TEXT = (
    "Теперь таймзона — выберите кнопкой или пришлите имя IANA текстом, например Europe/Moscow."
)
_ONBOARDING_CANCELLED_TEXT = "Настройка отменена. Чтобы начать заново, нажмите /start."
_ACCOUNT_TYPE_PROMPT_TEXT = "Какой счёт заводим первым?"
_OPENING_BALANCE_PROMPT_TEXT = (
    "Какой на нём сейчас остаток? Пришлите число (например, 15000 или "
    "1200,50) или нажмите «Начать с нуля»."
)
_HELP_TEXT = (
    "Команды:\n"
    "/start — регистрация или онбординг: базовая валюта, таймзона, первый счёт\n"
    "/menu — показать главное меню\n"
    "/expense, /income — сразу в нужный диалог\n"
    "/balance — остатки по всем счетам и итог в базовой валюте\n"
    "/today, /month — сводка расходов и доходов за день или текущий месяц\n"
    "/undo — сторнировать последнюю операцию, введённую в боте\n"
    "/cancel — выйти из любого диалога\n"
    "/help — эта справка\n\n"
    "Быстрый ввод одной строкой: [знак] сумма [валюта] [текст] [#категория] "
    "[@счёт] [!дата]. Примеры:\n"
    "-1200 кофе — расход 1200 RUB, категория по алиасу «кофе»\n"
    "+85000 зарплата — доход 85 000 RUB, категория «Зарплата»\n"
    "-3k такси @наличные !вчера — расход 3000 RUB, счёт «Наличные», вчера"
)


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, container: Container) -> None:
    """Регистрирует нового пользователя через онбординг либо здоровается."""
    if message.from_user is None:
        return
    existing = await container.find_user(
        FindUserByTelegramIdQuery(telegram_id=message.from_user.id)
    )
    await state.clear()
    if existing is not None:
        await message.answer(_WELCOME_BACK_TEXT, reply_markup=reply_keyboard())
        await message.answer("Главное меню", reply_markup=main_menu_keyboard())
        return

    await state.set_state(Onboarding.base_currency)
    await message.answer(_ONBOARDING_INTRO_TEXT, reply_markup=base_currency_keyboard())


@router.message(Command("cancel"), StateFilter(Onboarding))
async def handle_onboarding_cancel(message: Message, state: FSMContext) -> None:
    """Сбрасывает онбординг; следующий `/start` начинает его заново."""
    await state.clear()
    await message.answer(_ONBOARDING_CANCELLED_TEXT)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Отвечает справкой: команды этапа 1 и синтаксис быстрого ввода."""
    await message.answer(_HELP_TEXT)


@router.callback_query(
    OnboardingCallback.filter(F.step == "currency"), StateFilter(Onboarding.base_currency)
)
async def handle_base_currency(
    callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext
) -> None:
    """Шаг 1: сохраняет валюту и переходит к таймзоне."""
    await callback.answer()
    await state.update_data(base_currency=callback_data.value)
    await state.set_state(Onboarding.timezone)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(_TIMEZONE_PROMPT_TEXT, reply_markup=timezone_keyboard())


@router.callback_query(
    OnboardingCallback.filter(F.step == "timezone"), StateFilter(Onboarding.timezone)
)
async def handle_timezone_button(
    callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext
) -> None:
    """Шаг 2 кнопкой: сохраняет таймзону и переходит к типу счёта."""
    await callback.answer()
    await state.update_data(timezone=callback_data.value)
    await state.set_state(Onboarding.account_type)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _ACCOUNT_TYPE_PROMPT_TEXT, reply_markup=account_type_keyboard()
        )


@router.message(StateFilter(Onboarding.timezone), F.text & ~F.text.startswith("/"))
async def handle_timezone_text(message: Message, state: FSMContext) -> None:
    """Шаг 2 текстом: имя IANA, проверенное по `available_timezones()`."""
    value = (message.text or "").strip()
    if value not in available_timezones():
        await message.answer(input_error_message(BotInputError.UNKNOWN_TIMEZONE))
        return
    await state.update_data(timezone=value)
    await state.set_state(Onboarding.account_type)
    await message.answer(_ACCOUNT_TYPE_PROMPT_TEXT, reply_markup=account_type_keyboard())


@router.callback_query(
    OnboardingCallback.filter(F.step == "account_type"), StateFilter(Onboarding.account_type)
)
async def handle_account_type(
    callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext
) -> None:
    """Шаг 3: сохраняет тип счёта и переходит к начальному остатку."""
    await callback.answer()
    await state.update_data(account_type=callback_data.value)
    await state.set_state(Onboarding.opening_balance)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _OPENING_BALANCE_PROMPT_TEXT, reply_markup=opening_balance_keyboard()
        )


@router.callback_query(
    OnboardingCallback.filter(F.step == "opening_balance"), StateFilter(Onboarding.opening_balance)
)
async def handle_opening_balance_zero(
    callback: CallbackQuery, state: FSMContext, container: Container
) -> None:
    """Кнопка «Начать с нуля»: завершает онбординг с нулевым остатком."""
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    await _finish_onboarding(callback.message, container, state, callback.from_user, Decimal(0))


@router.message(StateFilter(Onboarding.opening_balance), F.text & ~F.text.startswith("/"))
async def handle_opening_balance_text(
    message: Message, state: FSMContext, container: Container
) -> None:
    """Начальный остаток текстом, в синтаксисе суммы быстрого ввода без знака."""
    if message.from_user is None:
        return
    amount = parse_amount(message.text or "")
    await _finish_onboarding(message, container, state, message.from_user, amount)


async def _finish_onboarding(
    reply_target: Message,
    container: Container,
    state: FSMContext,
    telegram_user: TelegramUser,
    opening_balance: Decimal,
) -> None:
    """Вызывает `RegisterUser`, очищает состояние и отвечает подтверждением.

    Ответ всегда новым сообщением (`reply_target.answer`), а не
    редактированием: `edit_text` не может добавить reply-клавиатуру
    (раздел 6.7), которую пользователь должен получить по итогам шага 4.
    """
    data = await state.get_data()
    await state.clear()
    account_type = AccountType(data["account_type"])
    command = RegisterUserCommand(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        base_currency=data["base_currency"],
        timezone=data["timezone"],
        account_name=ACCOUNT_TYPE_LABELS[account_type],
        account_type=account_type,
        opening_balance=opening_balance,
    )
    result = await container.register_user(command)

    balance_text = format_money(opening_balance, result.user.base_currency)
    text = (
        f"Готово! Счёт «{result.account.name}» создан, начальный остаток {balance_text}.\n\n"
        "Быстрый ввод: -1200 кофе — расход, +85000 зарплата — доход."
    )
    await reply_target.answer(text, reply_markup=reply_keyboard())
