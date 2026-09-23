"""DTO операций журнала.

`docs/architecture.md`, раздел 3.3 (`Transaction`, абзац «Форма сторно»).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from finplan.application.dto.base import Dto
from finplan.domain.entities.transaction import TransactionKind, TransactionStatus


class RecordTransactionCommand(Dto):
    """Команда записи операции в журнал.

    `occurred_at = None` означает «сейчас по `Clock`».
    """

    user_id: UUID
    kind: TransactionKind
    amount: Decimal = Field(gt=0)
    account_id: UUID
    category_id: UUID | None
    occurred_at: datetime | None
    comment: str | None
    external_key: str | None
    source: str


class TransactionDTO(Dto):
    """Снимок проведённой или сторнирующей операции."""

    id: UUID
    kind: TransactionKind
    status: TransactionStatus
    amount: Decimal
    currency: str
    account_id: UUID
    category_id: UUID | None
    occurred_at: datetime
    comment: str | None
    reverses_id: UUID | None
    created_at: datetime


class UndoLastCommand(Dto):
    """Команда отмены последней сторнируемой операции источника `source`."""

    user_id: UUID
    source: str


class UndoResultDTO(Dto):
    """Результат отмены: исходная операция и сторнирующая запись.

    Результат use case — `UndoResultDTO | None`, где `None` означает
    «нечего сторнировать».
    """

    original: TransactionDTO
    reversal: TransactionDTO
