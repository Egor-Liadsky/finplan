"""DTO счетов и остатков.

`docs/architecture.md`, раздел 3.3 (`Account`) и раздел 4.2 (остаток —
производная величина, а не хранимое поле).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from finplan.application.dto.base import Dto
from finplan.domain.entities.account import Account, AccountType


class AccountDTO(Dto):
    """Снимок счёта или актива пользователя."""

    id: UUID
    name: str
    type: AccountType
    currency: str
    opened_on: date
    is_archived: bool

    @classmethod
    def from_entity(cls, account: Account) -> AccountDTO:
        """Переводит доменный `Account` в DTO."""
        return cls(
            id=account.id,
            name=account.name,
            type=account.type,
            currency=account.currency.code,
            opened_on=account.opened_at,
            is_archived=account.is_archived,
        )


class ListAccountsQuery(Dto):
    """Запрос списка счетов пользователя."""

    user_id: UUID


class AccountListDTO(Dto):
    """Результат `ListAccountsQuery`."""

    items: tuple[AccountDTO, ...]


class GetBalancesQuery(Dto):
    """Запрос остатков по всем счетам пользователя."""

    user_id: UUID


class AccountBalanceDTO(Dto):
    """Остаток одного счёта в его собственной валюте."""

    account: AccountDTO
    balance: Decimal


class BalancesDTO(Dto):
    """Результат `GetBalancesQuery`: остатки по счетам и сумма в базовой валюте."""

    items: tuple[AccountBalanceDTO, ...]
    total: Decimal
    currency: str
