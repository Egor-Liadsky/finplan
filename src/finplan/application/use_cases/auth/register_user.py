"""Use case регистрации пользователя вместе с первым счётом.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»; раздел 3.3, таблицы `User` и `Account`, абзац «Дефолтный
набор» под таблицей `Category`.
"""

from __future__ import annotations

from uuid import uuid4
from zoneinfo import ZoneInfo

from finplan.application.dto.accounts import AccountDTO
from finplan.application.dto.auth import RegisterUserCommand, RegisterUserResult, UserDTO
from finplan.application.errors import InvalidCommandError, NotFoundError
from finplan.application.ports.clock import Clock
from finplan.application.ports.repositories import DuplicateError
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.common.currency import EUR, RUB, USD, Currency
from finplan.domain.common.money import Money
from finplan.domain.entities.account import Account
from finplan.domain.entities.category import build_default_categories
from finplan.domain.entities.user import User

# Раздел 3.1: справочник валют фиксированный, а поиска `Currency` по коду в
# домене нет — конструктору `Currency` ещё нужен `minor_unit`. Поиск по коду
# остаётся здесь и в домен не выносится.
_CURRENCIES: dict[str, Currency] = {currency.code: currency for currency in (RUB, USD, EUR)}


class RegisterUser:
    """Регистрирует пользователя с первым счётом либо возвращает уже существующего."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def __call__(self, command: RegisterUserCommand) -> RegisterUserResult:
        currency = _CURRENCIES.get(command.base_currency)
        if currency is None:
            raise InvalidCommandError(f"неизвестный код валюты: {command.base_currency!r}")

        new_id = uuid4()
        async with self._uow_factory(new_id) as uow:
            existing = await uow.users.get_by_telegram_id(command.telegram_id)
            if existing is None:
                now = self._clock.now()
                opened_at = now.astimezone(ZoneInfo(command.timezone)).date()
                user = User(
                    id=new_id,
                    telegram_id=command.telegram_id,
                    username=command.username,
                    first_name=command.first_name,
                    created_at=now,
                    base_currency=currency,
                    timezone=command.timezone,
                )
                account = Account(
                    id=uuid4(),
                    user_id=new_id,
                    name=command.account_name,
                    type=command.account_type,
                    currency=currency,
                    opening_balance=Money(command.opening_balance, currency),
                    opened_at=opened_at,
                )
                categories = build_default_categories(user_id=new_id, id_factory=uuid4)
                try:
                    await uow.users.add(user)
                    await uow.accounts.add(account)
                    await uow.categories.add_many(categories)
                    await uow.commit()
                except DuplicateError:
                    # Параллельный /start того же telegram_id успел раньше.
                    pass
                else:
                    return RegisterUserResult(
                        user=UserDTO.from_entity(user),
                        account=AccountDTO.from_entity(account),
                        created=True,
                    )

        if existing is None:
            async with self._uow_factory(None) as lookup_uow:
                existing = await lookup_uow.users.get_by_telegram_id(command.telegram_id)
            if existing is None:
                raise NotFoundError(f"пользователь с telegram_id={command.telegram_id} не найден")

        async with self._uow_factory(existing.id) as uow:
            accounts = await uow.accounts.list(existing.id)
        if not accounts:
            raise NotFoundError(f"у пользователя {existing.id} нет неархивных счетов")

        return RegisterUserResult(
            user=UserDTO.from_entity(existing),
            account=AccountDTO.from_entity(accounts[0]),
            created=False,
        )
