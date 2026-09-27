"""Сущность `Account`: счёт или актив.

`docs/architecture.md`, раздел 3.3, таблица `Account`, и раздел 3.2 для
`AccountType`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from finplan.domain.common.currency import Currency
from finplan.domain.common.errors import InvariantViolationError
from finplan.domain.common.money import Money


class AccountType(StrEnum):
    """Тип счёта или актива (раздел 3.2)."""

    CASH = "cash"
    BANK_ACCOUNT = "bank_account"
    CARD = "card"
    BROKER = "broker"
    REAL_ESTATE = "real_estate"
    DEPOSIT = "deposit"
    OTHER_ASSET = "other_asset"
    LIABILITY = "liability"


@dataclass(frozen=True, slots=True)
class Account:
    """Счёт или актив пользователя.

    Текущий остаток — производная величина (раздел 3.3, «Инварианты»):
    `opening_balance + Σ(приходы) − Σ(расходы)` по неотменённым операциям.
    Поэтому у сущности нет поля остатка — он не пересчитывается здесь.
    """

    id: UUID
    user_id: UUID
    name: str
    type: AccountType
    currency: Currency
    opening_balance: Money
    opened_at: date
    is_valuated: bool = False
    include_in_networth: bool = True
    is_archived: bool = False

    def __post_init__(self) -> None:
        if self.opening_balance.currency != self.currency:
            raise InvariantViolationError(
                "валюта opening_balance должна совпадать с валютой счёта: "
                f"{self.opening_balance.currency.code} != {self.currency.code}"
            )
