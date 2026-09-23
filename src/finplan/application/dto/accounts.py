"""DTO счетов и остатков.

`docs/architecture.md`, раздел 3.3 (`Account`) и раздел 4.2 (остаток —
производная величина, а не хранимое поле).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from finplan.application.dto.base import Dto
from finplan.domain.entities.account import AccountType


class AccountDTO(Dto):
    """Снимок счёта или актива пользователя."""

    id: UUID
    name: str
    type: AccountType
    currency: str
    is_archived: bool


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
