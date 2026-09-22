"""ORM-модель ``users``.

Столбцы и ограничения — `docs/architecture.md`, раздел 4.3, подраздел
`users`. Питоновское значение по умолчанию для `id` намеренно не задаётся:
UUIDv7 будет генерировать домен на этапе 1, здесь только тип столбца.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Boolean, DateTime, ForeignKey, Text, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from finplan.infrastructure.db.base import Base


class User(Base):
    """Пользователь Telegram-бота и веб-интерфейса."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_currency: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code"), nullable=False, server_default="RUB"
    )
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="Europe/Moscow")
    locale: Mapped[str] = mapped_column(Text, nullable=False, server_default="ru")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
