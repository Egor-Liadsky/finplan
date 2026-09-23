"""DTO аутентификации и регистрации пользователя.

`docs/architecture.md`, раздел 3.3 (`User`, `Account`).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from finplan.application.dto.accounts import AccountDTO
from finplan.application.dto.base import Dto
from finplan.domain.entities.account import AccountType


class UserDTO(Dto):
    """Снимок пользователя для верхних слоёв."""

    id: UUID
    telegram_id: int
    username: str | None
    first_name: str
    base_currency: str
    timezone: str
    locale: str


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
