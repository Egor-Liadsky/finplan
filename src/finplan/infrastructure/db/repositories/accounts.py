"""`SqlAlchemyAccountRepository`: доступ к счетам и активам пользователя.

`docs/architecture.md`, раздел 4.3, таблица `accounts`, и раздел 4.5,
ADR-008: репозиторий фильтрует по `user_id` явно, даже при включённом RLS.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from finplan.application.ports.repositories import AccountRepository, DuplicateError
from finplan.domain.common.currency import Currency
from finplan.domain.common.money import Money
from finplan.domain.entities.account import Account, AccountType
from finplan.infrastructure.db.models.accounts import Account as AccountModel
from finplan.infrastructure.db.models.currencies import Currency as CurrencyModel

# Код ошибки PostgreSQL `unique_violation` (раздел 12.3), см. пояснение в
# `repositories/users.py`.
_UNIQUE_VIOLATION = "23505"


class SqlAlchemyAccountRepository:
    """Репозиторий счетов поверх `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID, account_id: UUID) -> Account | None:
        stmt = (
            select(AccountModel, CurrencyModel.minor_unit)
            .join(CurrencyModel, AccountModel.currency == CurrencyModel.code)
            .where(AccountModel.user_id == user_id, AccountModel.id == account_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        model, minor_unit = row
        return _to_domain(model, minor_unit)

    async def list(self, user_id: UUID, *, include_archived: bool = False) -> Sequence[Account]:
        stmt = (
            select(AccountModel, CurrencyModel.minor_unit)
            .join(CurrencyModel, AccountModel.currency == CurrencyModel.code)
            .where(AccountModel.user_id == user_id)
            .order_by(AccountModel.sort_order, AccountModel.created_at)
        )
        if not include_archived:
            stmt = stmt.where(AccountModel.is_archived.is_(False))
        rows = (await self._session.execute(stmt)).all()
        return [_to_domain(model, minor_unit) for model, minor_unit in rows]

    async def add(self, account: Account) -> None:
        model = AccountModel(
            id=account.id,
            user_id=account.user_id,
            name=account.name,
            type=account.type.value,
            currency=account.currency.code,
            opening_balance=account.opening_balance.amount,
            opened_on=account.opened_at,
            is_valuated=account.is_valuated,
            include_in_networth=account.include_in_networth,
            is_archived=account.is_archived,
            # Раздел 4.3: `created_at` у `accounts`, в отличие от `users` и
            # `transactions`, без `server_default` в БД. `Account` не хранит
            # момент создания строки — это учётная метка инфраструктуры, а
            # не доменное поле, поэтому подставляется здесь.
            created_at=datetime.now(UTC),
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise DuplicateError(
                    f"у пользователя {account.user_id} уже есть счёт с именем {account.name!r}"
                ) from exc
            raise


def _to_domain(model: AccountModel, minor_unit: int) -> Account:
    currency = Currency(code=model.currency, minor_unit=minor_unit)
    return Account(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        type=AccountType(model.type),
        currency=currency,
        opening_balance=Money(amount=model.opening_balance, currency=currency),
        opened_at=model.opened_on,
        is_valuated=model.is_valuated,
        include_in_networth=model.include_in_networth,
        is_archived=model.is_archived,
    )


if TYPE_CHECKING:
    _check: type[AccountRepository] = SqlAlchemyAccountRepository
