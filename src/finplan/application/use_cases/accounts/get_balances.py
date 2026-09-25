"""Use case `GetBalances`: остатки по счетам пользователя.

`docs/architecture.md`, раздел 6.1 (`/balance`) и раздел 4.2 — остаток счёта
не хранится, а пересчитывается из `opening_balance` и движений журнала.
"""

from __future__ import annotations

from decimal import Decimal

from finplan.application.dto.accounts import (
    AccountBalanceDTO,
    AccountDTO,
    BalancesDTO,
    GetBalancesQuery,
)
from finplan.application.errors import NotFoundError
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.common.money import Money


class GetBalances:
    """Остатки неархивных счетов пользователя и сумма в базовой валюте."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, query: GetBalancesQuery) -> BalancesDTO:
        async with self._uow_factory(query.user_id) as uow:
            user = await uow.users.get(query.user_id)
            if user is None:
                raise NotFoundError(f"пользователь {query.user_id} не найден")

            accounts = await uow.accounts.list(query.user_id)
            movements = await uow.ledger.account_movements(query.user_id)

        items: list[AccountBalanceDTO] = []
        total = Money.zero(user.base_currency)
        for account in accounts:
            movement = movements.get(account.id, Decimal(0))
            balance = account.opening_balance + Money(amount=movement, currency=account.currency)
            items.append(
                AccountBalanceDTO(account=AccountDTO.from_entity(account), balance=balance.amount)
            )
            if account.include_in_networth:
                total = total + balance

        return BalancesDTO(items=tuple(items), total=total.amount, currency=user.base_currency.code)
