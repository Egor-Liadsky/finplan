"""Use case `ListCategories`: список неархивных категорий заданного вида.

`docs/architecture.md`, раздел 6.1 — клавиатура выбора категории.
"""

from __future__ import annotations

from finplan.application.dto.categories import (
    CategoryDTO,
    CategoryListDTO,
    ListCategoriesQuery,
)
from finplan.application.ports.uow import UnitOfWorkFactory


class ListCategories:
    """Возвращает неархивные категории пользователя заданного вида."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, query: ListCategoriesQuery) -> CategoryListDTO:
        async with self._uow_factory(query.user_id) as uow:
            categories = await uow.categories.list(query.user_id, query.kind)
        return CategoryListDTO(
            items=tuple(CategoryDTO.from_entity(category) for category in categories)
        )
