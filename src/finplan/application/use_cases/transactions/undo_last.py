"""Use case отмены последней сторнируемой операции журнала.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»; раздел 3.3, абзац «Форма сторно»; раздел 4.2 — исходная
операция не изменяется и не удаляется, только помечается `reversed`.
"""

from __future__ import annotations

from uuid import uuid4

from finplan.application.dto.transactions import (
    TransactionDTO,
    UndoLastCommand,
    UndoResultDTO,
)
from finplan.application.ports.clock import Clock
from finplan.application.ports.uow import UnitOfWorkFactory


class UndoLastTransaction:
    """Сторнирует последнюю сторнируемую операцию источника `source`."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def __call__(self, command: UndoLastCommand) -> UndoResultDTO | None:
        async with self._uow_factory(command.user_id) as uow:
            original = await uow.transactions.last_reversible(command.user_id, command.source)
            if original is None:
                return None

            reversed_original, reversal = original.reverse(
                reversal_id=uuid4(), created_at=self._clock.now()
            )
            await uow.transactions.mark_reversed(command.user_id, reversed_original.id)
            await uow.transactions.add(reversal)
            await uow.commit()

        return UndoResultDTO(
            original=TransactionDTO.from_entity(reversed_original),
            reversal=TransactionDTO.from_entity(reversal),
        )
