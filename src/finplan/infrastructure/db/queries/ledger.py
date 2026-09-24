"""Реализация `LedgerQueries` поверх одной `AsyncSession`.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»: `ledger` учитывает только операции в статусе `posted`, работает
в той же сессии, что и репозитории Unit of Work, и не требует своей
транзакции.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import case, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from finplan.application.ports.repositories import CategoryTotal, LedgerQueries
from finplan.domain.entities.transaction import TransactionKind, TransactionStatus
from finplan.infrastructure.db.models.transactions import Transaction as TransactionRow


class SqlAlchemyLedgerQueries:
    """Чтение агрегатов журнала операций поверх одной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def account_movements(self, user_id: UUID) -> Mapping[UUID, Decimal]:
        """Сумма движений по каждому счёту в валюте счёта (докstring порта, 5.7).

        Кросс-валютная пара строк `transfer_group_id` из раздела 3.3
        решается на этапе 2 (домен пока не заводит поле `transfer_group_id`
        и не создаёт переводы); здесь один перевод — одна строка, и
        `transfer_group_id` в запросе не участвует.
        """
        debit = select(
            TransactionRow.account_id.label("account_id"),
            case(
                (TransactionRow.kind == TransactionKind.INCOME.value, TransactionRow.amount),
                (
                    TransactionRow.kind.in_(
                        (TransactionKind.EXPENSE.value, TransactionKind.TRANSFER.value)
                    ),
                    -TransactionRow.amount,
                ),
            ).label("signed_amount"),
        ).where(
            TransactionRow.user_id == user_id,
            TransactionRow.status == TransactionStatus.POSTED.value,
            TransactionRow.kind.in_(
                (
                    TransactionKind.INCOME.value,
                    TransactionKind.EXPENSE.value,
                    TransactionKind.TRANSFER.value,
                )
            ),
        )
        credit = select(
            TransactionRow.counter_account_id.label("account_id"),
            TransactionRow.amount.label("signed_amount"),
        ).where(
            TransactionRow.user_id == user_id,
            TransactionRow.status == TransactionStatus.POSTED.value,
            TransactionRow.kind == TransactionKind.TRANSFER.value,
        )
        movements = union_all(debit, credit).subquery("movements")
        stmt = select(movements.c.account_id, func.sum(movements.c.signed_amount)).group_by(
            movements.c.account_id
        )
        result = await self._session.execute(stmt)
        return {account_id: total for account_id, total in result.all()}

    async def totals_by_category(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> Sequence[CategoryTotal]:
        """Суммы `base_amount` операций `income`/`expense` по категориям.

        Только `status = posted`, только операции с заданной категорией,
        `occurred_at` в полуинтервале `[start, end)`.
        """
        total = func.sum(TransactionRow.base_amount)
        stmt = (
            select(TransactionRow.category_id, TransactionRow.kind, total)
            .where(
                TransactionRow.user_id == user_id,
                TransactionRow.status == TransactionStatus.POSTED.value,
                TransactionRow.kind.in_(
                    (TransactionKind.INCOME.value, TransactionKind.EXPENSE.value)
                ),
                TransactionRow.category_id.is_not(None),
                TransactionRow.occurred_at >= start,
                TransactionRow.occurred_at < end,
            )
            .group_by(TransactionRow.category_id, TransactionRow.kind)
        )
        result = await self._session.execute(stmt)
        return [
            CategoryTotal(
                category_id=category_id,
                kind=TransactionKind(kind),
                base_amount=base_amount,
            )
            for category_id, kind, base_amount in result.all()
        ]


if TYPE_CHECKING:
    _check: type[LedgerQueries] = SqlAlchemyLedgerQueries
