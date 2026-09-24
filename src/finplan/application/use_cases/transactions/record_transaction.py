"""Use case записи операции дохода или расхода в журнал.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»; раздел 3.3, таблица `Transaction`; раздел 12.3 про
идемпотентность по `external_key`.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from finplan.application.dto.transactions import RecordTransactionCommand, TransactionDTO
from finplan.application.errors import InvalidCommandError, NotFoundError
from finplan.application.ports.clock import Clock
from finplan.application.ports.uow import UnitOfWorkFactory
from finplan.domain.common.money import Money
from finplan.domain.entities.category import CategoryKind
from finplan.domain.entities.transaction import Transaction, TransactionKind, TransactionStatus

# Раздел 3.3: перевод (`transfer`) — этап 2, здесь допустимы только доход и
# расход, каждый привязан к категории того же вида.
_CATEGORY_KIND_BY_TRANSACTION_KIND = {
    TransactionKind.EXPENSE: CategoryKind.EXPENSE,
    TransactionKind.INCOME: CategoryKind.INCOME,
}


class RecordTransaction:
    """Записывает операцию дохода или расхода в журнал пользователя."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def __call__(self, command: RecordTransactionCommand) -> TransactionDTO:
        expected_category_kind = _CATEGORY_KIND_BY_TRANSACTION_KIND.get(command.kind)
        if expected_category_kind is None:
            raise InvalidCommandError(
                "RecordTransaction поддерживает только expense и income, "
                f"получено {command.kind.value}"
            )

        async with self._uow_factory(command.user_id) as uow:
            user = await uow.users.get(command.user_id)
            if user is None:
                raise NotFoundError(f"пользователь {command.user_id} не найден")

            account = await uow.accounts.get(command.user_id, command.account_id)
            if account is None or account.is_archived:
                raise NotFoundError(f"счёт {command.account_id} не найден или архивирован")

            if command.category_id is not None:
                category = await uow.categories.get(command.user_id, command.category_id)
                if category is None or category.is_archived:
                    raise NotFoundError(
                        f"категория {command.category_id} не найдена или архивирована"
                    )
                if category.kind is not expected_category_kind:
                    raise InvalidCommandError(
                        f"категория вида {category.kind.value} не подходит для "
                        f"операции {command.kind.value}"
                    )

            if account.currency != user.base_currency:
                raise InvalidCommandError(
                    "валюта счёта должна совпадать с базовой валютой пользователя: "
                    "курсов на этапе 1 нет"
                )

            # Раздел 3.1, таблица округления: хранение операции, введённой
            # пользователем, — ROUND_HALF_UP до minor_unit валюты счёта. На
            # этапе 1 курс равен 1, поэтому base_amount обязана совпасть с
            # округлённой amount до знака.
            rounded_amount = Money(command.amount, account.currency).round_to_minor_unit()
            if rounded_amount.amount == 0:
                raise InvalidCommandError(
                    "сумма операции после округления до минорной единицы равна нулю"
                )

            now = self._clock.now()
            occurred_at = command.occurred_at or now
            transaction = Transaction.new(
                id=uuid4(),
                user_id=command.user_id,
                kind=command.kind,
                status=TransactionStatus.POSTED,
                amount=rounded_amount,
                account_id=account.id,
                category_id=command.category_id,
                occurred_at=occurred_at,
                comment=command.comment,
                base_amount=rounded_amount.amount,
                base_currency=user.base_currency,
                base_rate=Decimal(1),
                source=command.source,
                external_key=command.external_key,
                created_at=now,
                now=now,
            )
            await uow.transactions.add(transaction)
            await uow.commit()

        return TransactionDTO.from_entity(transaction)
