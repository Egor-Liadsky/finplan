"""`SqlAlchemyCategoryRepository`: доступ к категориям пользователя.

`docs/architecture.md`, раздел 4.3, таблица `categories`, и раздел 4.5,
ADR-008: репозиторий фильтрует по `user_id` явно, даже при включённом RLS.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from finplan.application.ports.repositories import CategoryRepository, DuplicateError
from finplan.domain.entities.category import Category, CategoryKind
from finplan.infrastructure.db.models.categories import Category as CategoryModel

# Код ошибки PostgreSQL `unique_violation` (раздел 12.3), см. пояснение в
# `repositories/users.py`.
_UNIQUE_VIOLATION = "23505"


class SqlAlchemyCategoryRepository:
    """Репозиторий категорий поверх `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID, category_id: UUID) -> Category | None:
        stmt = select(CategoryModel).where(
            CategoryModel.user_id == user_id, CategoryModel.id == category_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def list(
        self, user_id: UUID, kind: CategoryKind, *, include_archived: bool = False
    ) -> Sequence[Category]:
        stmt = (
            select(CategoryModel)
            .where(CategoryModel.user_id == user_id, CategoryModel.kind == kind.value)
            .order_by(CategoryModel.sort_order)
        )
        if not include_archived:
            stmt = stmt.where(CategoryModel.is_archived.is_(False))
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def add_many(self, categories: Sequence[Category]) -> None:
        for category in categories:
            self._session.add(
                CategoryModel(
                    id=category.id,
                    user_id=category.user_id,
                    parent_id=category.parent_id,
                    kind=category.kind.value,
                    name=category.name,
                    path=category.path,
                    depth=category.depth,
                    icon=None,
                    is_archived=category.is_archived,
                    sort_order=category.sort_order,
                    aliases=list(category.aliases),
                )
            )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise DuplicateError(
                    "категория с таким path уже существует у пользователя"
                ) from exc
            raise


def _to_domain(model: CategoryModel) -> Category:
    return Category(
        id=model.id,
        user_id=model.user_id,
        parent_id=model.parent_id,
        kind=CategoryKind(model.kind),
        name=model.name,
        path=model.path,
        depth=model.depth,
        is_archived=model.is_archived,
        sort_order=model.sort_order,
        aliases=tuple(model.aliases),
    )


if TYPE_CHECKING:
    _check: type[CategoryRepository] = SqlAlchemyCategoryRepository
