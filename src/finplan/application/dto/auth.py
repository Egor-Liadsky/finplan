"""DTO аутентификации и регистрации пользователя.

`docs/architecture.md`, раздел 3.3 (`User`, `Account`).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from finplan.application.dto.accounts import AccountDTO
from finplan.application.dto.base import Dto
from finplan.domain.entities.account import AccountType
from finplan.domain.entities.user import User


class UserDTO(Dto):
    """Снимок пользователя для верхних слоёв."""

    id: UUID
    telegram_id: int
    username: str | None
    first_name: str
    base_currency: str
    timezone: str
    locale: str

    @classmethod
    def from_entity(cls, user: User) -> UserDTO:
        """Переводит доменного `User` в DTO."""
        return cls(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            base_currency=user.base_currency.code,
            timezone=user.timezone,
            locale=user.locale,
        )


class RegisterUserCommand(Dto):
    """Команда регистрации пользователя вместе с первым счётом."""

    telegram_id: int
    username: str | None
    first_name: str
    base_currency: str
    timezone: str
    account_name: str
    account_type: AccountType
    opening_balance: Decimal


class RegisterUserResult(Dto):
    """Результат регистрации: пользователь, первый счёт и признак создания.

    `created` ложно, если пользователь с этим `telegram_id` уже существовал.
    """

    user: UserDTO
    account: AccountDTO
    created: bool


class FindUserByTelegramIdQuery(Dto):
    """Запрос пользователя по `telegram_id`.

    Результат use case — `UserDTO | None`, отдельной модели результата нет.
    """

    telegram_id: int
