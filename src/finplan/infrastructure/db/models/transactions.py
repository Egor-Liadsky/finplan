"""ORM-модель ``transactions``.

Столбцы, ограничения и индексы — `docs/architecture.md`, раздел 4.3,
подраздел `transactions`. Иммутабельность (`trg_transactions_immutable`) —
триггер на уровне БД, заводится в миграции, а не здесь: модель описывает
только форму таблицы.

`deposit_id`, `goal_id` и `recurring_rule_id` объявлены без
`ForeignKey`: таблицы `deposits`, `savings_goals` и `recurring_rules`
раздела 4.3 в эту подзадачу (8a плана этапа 1) не входят — их заводят
более поздние этапы. Столбцы нужны уже сейчас, потому что на них ссылается
доменная сущность `Transaction` (`recurring_rule_id`, `deposit_id`,
`goal_id`), а FK-ограничения добавятся отдельной миграцией вместе с
таблицами-целями.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from finplan.infrastructure.db.base import Base

_ALLOWED_KINDS = ("income", "expense", "transfer", "adjustment", "interest")
_ALLOWED_STATUSES = ("posted", "reversed", "pending")
_ALLOWED_SOURCES = ("bot", "web", "recurring", "system", "import")


def _in_list(*values: str) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Transaction(Base):
    """Операция неизменяемого журнала (раздел 4.2)."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_in_list(*_ALLOWED_KINDS)})", name="kind_allowed"),
        CheckConstraint(f"status IN ({_in_list(*_ALLOWED_STATUSES)})", name="status_allowed"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("comment IS NULL OR length(comment) <= 500", name="comment_length"),
        CheckConstraint("base_rate > 0", name="base_rate_positive"),
        CheckConstraint(f"source IN ({_in_list(*_ALLOWED_SOURCES)})", name="source_allowed"),
        CheckConstraint(
            "(kind = 'transfer' AND counter_account_id IS NOT NULL "
            "AND counter_account_id <> account_id AND category_id IS NULL) "
            "OR (kind <> 'transfer' AND counter_account_id IS NULL)",
            name="transfer_shape",
        ),
        CheckConstraint(
            "(kind IN ('income', 'expense') AND category_id IS NOT NULL) "
            "OR kind NOT IN ('income', 'expense')",
            name="category_required",
        ),
        UniqueConstraint("user_id", "external_key"),
        UniqueConstraint("reverses_id"),
        Index("ix_transactions_user_id_occurred_at", "user_id", text("occurred_at DESC")),
        Index("ix_transactions_user_id_occurred_on_kind", "user_id", "occurred_on", "kind"),
        Index("ix_transactions_account_id_occurred_at", "account_id", "occurred_at"),
        Index(
            "ix_transactions_category_id_occurred_on",
            "category_id",
            "occurred_on",
            postgresql_where=text("status = 'posted'"),
        ),
        Index(
            "ix_transactions_deposit_id_occurred_at",
            "deposit_id",
            "occurred_at",
            postgresql_where=text("deposit_id IS NOT NULL"),
        ),
        Index(
            "ix_transactions_goal_id",
            "goal_id",
            postgresql_where=text("goal_id IS NOT NULL"),
        ),
        Index(
            "ix_transactions_pending",
            "user_id",
            "occurred_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), ForeignKey("currencies.code"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    counter_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Дата в таймзоне пользователя, denormalized для группировок (раздел 4.3).
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code"), nullable=False
    )
    base_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    # Связывает две половины перевода; не FK — обе половины равноправны.
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # Без ForeignKey: таблицы deposits, savings_goals, recurring_rules не
    # входят в эту подзадачу — см. docstring модуля.
    deposit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    recurring_rule_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    external_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
