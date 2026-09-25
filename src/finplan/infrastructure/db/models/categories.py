"""ORM-модель ``categories``.

Столбцы и ограничения — `docs/architecture.md`, раздел 4.3, подраздел
`categories`, включая столбец `aliases`, добавленный туда же для разрешения
категорий из быстрого ввода (раздел 6.5).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from finplan.infrastructure.db.base import Base

_ALLOWED_KINDS = ("income", "expense")


class Category(Base):
    """Категория дохода или расхода в иерархии пользователя."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "path"),
        CheckConstraint("id <> parent_id", name="no_self_parent"),
        CheckConstraint(
            "kind IN ({})".format(", ".join(f"'{value}'" for value in _ALLOWED_KINDS)),
            name="kind_allowed",
        ),
        CheckConstraint("depth BETWEEN 0 AND 2", name="depth_range"),
        Index("ix_categories_user_id_kind", "user_id", "kind"),
        # text_pattern_ops на path — запросы поддерева `path LIKE 'food.%'`.
        Index(
            "ix_categories_user_id_path",
            "user_id",
            "path",
            postgresql_ops={"path": "text_pattern_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
