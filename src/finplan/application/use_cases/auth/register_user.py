"""Use case регистрации пользователя вместе с первым счётом.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»; раздел 3.3, таблицы `User` и `Account`, абзац «Дефолтный
набор» под таблицей `Category`.
"""

from __future__ import annotations

from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

        try:
            tzinfo = ZoneInfo(command.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise InvalidCommandError(f"неизвестная таймзона: {command.timezone!r}") from exc

        # Раздел 2.2: `None` в фабрике UoW допустим только для поиска
        # пользователя по telegram_id, пока его id неизвестен. Поиск ведём
        # отдельной транзакцией до открытия транзакции от имени new_id —
        # иначе под RLS раздела 4.5 поиск существующего пользователя в
        # транзакции ещё не созданного new_id промахивается.
        async with self._uow_factory(None) as lookup_uow:
            existing = await lookup_uow.users.get_by_telegram_id(command.telegram_id)

        if existing is None:
            new_id = uuid4()
            now = self._clock.now()
            opened_at = now.astimezone(tzinfo).date()
            # Раздел 3.1, таблица округления: сумма, введённая пользователем,
            # — ROUND_HALF_UP до minor_unit валюты. Нулевой начальный остаток
            # допустим.
            opening_balance = Money(command.opening_balance, currency).round_to_minor_unit()
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
                opening_balance=opening_balance,
                opened_at=opened_at,
            )
            categories = build_default_categories(user_id=new_id, id_factory=uuid4)
            try:
                async with self._uow_factory(new_id) as uow:
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
