"""`SqlAlchemyTransactionRepository`: доступ к журналу операций пользователя.

`docs/architecture.md`, раздел 4.3, таблица `transactions`; раздел 4.2 —
неизменяемость журнала: `mark_reversed` меняет только столбец `status` и
только при условии `status = 'posted'`, другой `UPDATE` и `DELETE` запрещены
триггером `trg_transactions_immutable`; раздел 4.5, ADR-008 — репозиторий
фильтрует по `user_id` явно, даже при включённом RLS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from finplan.application.ports.repositories import DuplicateError, TransactionRepository
from finplan.domain.common.currency import Currency
from finplan.domain.common.money import Money
from finplan.domain.entities.transaction import Transaction, TransactionKind, TransactionStatus
from finplan.infrastructure.db.models.currencies import Currency as CurrencyModel
from finplan.infrastructure.db.models.transactions import Transaction as TransactionModel

# Код ошибки PostgreSQL `unique_violation` (раздел 12.3), см. пояснение в
# `repositories/users.py`.
_UNIQUE_VIOLATION = "23505"


class SqlAlchemyTransactionRepository:
    """Репозиторий журнала операций поверх `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID, transaction_id: UUID) -> Transaction | None:
        stmt = select(TransactionModel).where(
            TransactionModel.user_id == user_id, TransactionModel.id == transaction_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model, await self._minor_units(model.currency, model.base_currency))

    async def add(self, transaction: Transaction) -> None:
        model = TransactionModel(
            id=transaction.id,
            user_id=transaction.user_id,
            kind=transaction.kind.value,
            status=transaction.status.value,
            amount=transaction.amount.amount,
            currency=transaction.amount.currency.code,
            account_id=transaction.account_id,
            counter_account_id=transaction.counter_account_id,
            category_id=transaction.category_id,
            occurred_at=transaction.occurred_at,
            occurred_on=transaction.occurred_on,
            comment=transaction.comment,
            base_amount=transaction.base_amount,
            base_currency=transaction.base_currency.code,
            base_rate=transaction.base_rate,
            # Раздел 4.3: связывает две половины перевода. `Transaction` его
            # не хранит, а `RecordTransaction` этапа 1 переводов не создаёт
            # (раздел 2.2 use case поддерживает только income/expense),
            # поэтому здесь всегда `NULL`.
            transfer_group_id=None,
            deposit_id=transaction.deposit_id,
            goal_id=transaction.goal_id,
            recurring_rule_id=transaction.recurring_rule_id,
            reverses_id=transaction.reverses_id,
            external_key=transaction.external_key,
            source=transaction.source,
            created_at=transaction.created_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise DuplicateError(
                    f"операция с external_key {transaction.external_key!r} уже сохранена"
                ) from exc
            raise

    async def mark_reversed(self, user_id: UUID, transaction_id: UUID) -> None:
        # Раздел 4.2: единственное разрешённое изменение строки журнала —
        # переход `status` из `posted` в `reversed`; условие `status =
        # 'posted'` в WHERE — не только фильтр, но и защита от двойного
        # сторно той же строки в конкурентном вызове.
        stmt = (
            update(TransactionModel)
            .where(
                TransactionModel.user_id == user_id,
                TransactionModel.id == transaction_id,
                TransactionModel.status == TransactionStatus.POSTED.value,
            )
            .values(status=TransactionStatus.REVERSED.value)
        )
        await self._session.execute(stmt)

    async def last_reversible(self, user_id: UUID, source: str) -> Transaction | None:
        stmt = (
            select(TransactionModel)
            .where(
                TransactionModel.user_id == user_id,
                TransactionModel.source == source,
                TransactionModel.status == TransactionStatus.POSTED.value,
                TransactionModel.reverses_id.is_(None),
            )
            .order_by(TransactionModel.created_at.desc())
            .limit(1)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model, await self._minor_units(model.currency, model.base_currency))

    async def _minor_units(self, currency_code: str, base_currency_code: str) -> dict[str, int]:
        codes = {currency_code, base_currency_code}
        stmt = select(CurrencyModel.code, CurrencyModel.minor_unit).where(
            CurrencyModel.code.in_(codes)
        )
        rows = (await self._session.execute(stmt)).all()
        return {code: minor_unit for code, minor_unit in rows}


def _to_domain(model: TransactionModel, minor_units: dict[str, int]) -> Transaction:
    currency = Currency(code=model.currency, minor_unit=minor_units[model.currency])
    base_currency = Currency(code=model.base_currency, minor_unit=minor_units[model.base_currency])
    return Transaction(
        id=model.id,
        user_id=model.user_id,
        kind=TransactionKind(model.kind),
        status=TransactionStatus(model.status),
        amount=Money(amount=model.amount, currency=currency),
        account_id=model.account_id,
        counter_account_id=model.counter_account_id,
        category_id=model.category_id,
        occurred_at=model.occurred_at,
        occurred_on=model.occurred_on,
        comment=model.comment,
        base_amount=model.base_amount,
        base_currency=base_currency,
        base_rate=model.base_rate,
        external_key=model.external_key,
        source=model.source,
        recurring_rule_id=model.recurring_rule_id,
        deposit_id=model.deposit_id,
        goal_id=model.goal_id,
        reverses_id=model.reverses_id,
        created_at=model.created_at,
    )


if TYPE_CHECKING:
    _check: type[TransactionRepository] = SqlAlchemyTransactionRepository
