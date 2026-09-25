"""DTO категорий доходов и расходов.

`docs/architecture.md`, раздел 3.3 (`Category`).
"""

from __future__ import annotations

from uuid import UUID

from finplan.application.dto.base import Dto
from finplan.domain.entities.category import Category, CategoryKind


class CategoryDTO(Dto):
    """Снимок категории в иерархии пользователя."""

    id: UUID
    parent_id: UUID | None
    kind: CategoryKind
    name: str
    path: str
    depth: int

    @classmethod
    def from_entity(cls, category: Category) -> CategoryDTO:
        """Переводит доменную `Category` в DTO."""
        return cls(
            id=category.id,
            parent_id=category.parent_id,
            kind=category.kind,
            name=category.name,
            path=category.path,
            depth=category.depth,
        )


class ListCategoriesQuery(Dto):
    """Запрос категорий пользователя заданного вида."""

    user_id: UUID
    kind: CategoryKind


class CategoryListDTO(Dto):
    """Результат `ListCategoriesQuery`."""

    items: tuple[CategoryDTO, ...]
