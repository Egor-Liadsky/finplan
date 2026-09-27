"""ORM-модель ``accounts``.

Столбцы и ограничения — `docs/architecture.md`, раздел 4.3, подраздел
`accounts`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    Uuid,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from finplan.infrastructure.db.base import Base

_ALLOWED_TYPES = (
    "cash",
    "bank_account",
    "card",
    "broker",
    "real_estate",
    "deposit",
    "other_asset",
    "liability",
)


class Account(Base):
    """Счёт или актив пользователя."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 100", name="name_length"),
        CheckConstraint(
            "type IN ({})".format(", ".join(f"'{value}'" for value in _ALLOWED_TYPES)),
            name="type_allowed",
        ),
        # Частичный уникальный индекс, а не UniqueConstraint: WHERE-условие
        # поддерживает только Index.
        Index(
            "uq_accounts_user_id_name",
            "user_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("NOT is_archived"),
        ),
        Index("ix_accounts_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), ForeignKey("currencies.code"), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, server_default="0"
    )
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    is_valuated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    include_in_networth: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Без server_default: раздел 4.3 не задаёт DEFAULT для created_at здесь,
    # в отличие от users и transactions — значение подставляет приложение.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
