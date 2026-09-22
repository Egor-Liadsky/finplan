"""ORM-модель ``currencies``.

Столбцы и ограничения — `docs/architecture.md`, раздел 4.3, подраздел
`currencies`.
"""

from __future__ import annotations

from sqlalchemy import CHAR, Boolean, CheckConstraint, SmallInteger, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from finplan.infrastructure.db.base import Base


class Currency(Base):
    """Справочник валют: PK — трёхбуквенный код ISO 4217."""

    __tablename__ = "currencies"
    __table_args__ = (CheckConstraint("minor_unit BETWEEN 0 AND 4", name="minor_unit_range"),)

    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(Text, nullable=True)
    minor_unit: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
