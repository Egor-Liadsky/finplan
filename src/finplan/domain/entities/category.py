"""Сущность `Category`: иерархия категорий доходов и расходов.

`docs/architecture.md`, раздел 3.3, таблица `Category` и абзацы под ней про
слаги и дефолтный набор; раздел 3.2 для `CategoryKind`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from finplan.domain.common.errors import InvariantViolationError

#: Раздел 3.3: слаг — латиница в нижнем регистре, цифры и `_`, начинается с буквы.
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

#: Раздел 3.3: глубина набора — три уровня, `depth` от 0 до 2 включительно.
MAX_DEPTH = 2


class CategoryKind(StrEnum):
    """Вид категории: доход или расход (раздел 3.2)."""

    INCOME = "income"
    EXPENSE = "expense"


@dataclass(frozen=True, slots=True)
class Category:
    """Категория дохода или расхода в иерархии пользователя."""

    id: UUID
    user_id: UUID
    parent_id: UUID | None
    kind: CategoryKind
    name: str
    path: str
    depth: int
    is_archived: bool = False
    sort_order: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.depth <= MAX_DEPTH:
            raise InvariantViolationError(f"depth должен быть от 0 до {MAX_DEPTH}: {self.depth!r}")
        segments = self.path.split(".")
        if len(segments) != self.depth + 1:
            raise InvariantViolationError(f"path {self.path!r} не соответствует depth={self.depth}")
        for segment in segments:
            if not SLUG_PATTERN.fullmatch(segment):
                raise InvariantViolationError(
                    f"слаг {segment!r} не соответствует {SLUG_PATTERN.pattern!r}"
                )
        if self.depth == 0 and self.parent_id is not None:
            raise InvariantViolationError("корневая категория не может иметь parent_id")
        if self.depth > 0 and self.parent_id is None:
            raise InvariantViolationError("некорневая категория обязана иметь parent_id")

    @classmethod
    def new_root(
        cls,
        *,
        id: UUID,
        user_id: UUID,
        kind: CategoryKind,
        slug: str,
        name: str,
        sort_order: int = 0,
        is_archived: bool = False,
    ) -> Category:
        """Корневая категория (`depth = 0`, без родителя)."""
        return cls(
            id=id,
            user_id=user_id,
            parent_id=None,
            kind=kind,
            name=name,
            path=slug,
            depth=0,
            is_archived=is_archived,
            sort_order=sort_order,
        )

    @classmethod
    def new_child(
        cls,
        *,
        id: UUID,
        parent: Category,
        slug: str,
        name: str,
        sort_order: int = 0,
        is_archived: bool = False,
    ) -> Category:
        """Дочерняя категория: `path`, `depth` и `kind` берутся у `parent`.

        `kind` дочерней категории копируется из `parent` — так инвариант
        «kind совпадает с родительским» (раздел 3.3) не может быть нарушен
        через эту фабрику.
        """
        if parent.depth >= MAX_DEPTH:
            raise InvariantViolationError(
                f"у категории глубины {parent.depth} не может быть потомка (максимум {MAX_DEPTH})"
            )
        return cls(
            id=id,
            user_id=parent.user_id,
            parent_id=parent.id,
            kind=parent.kind,
            name=name,
            path=f"{parent.path}.{slug}",
            depth=parent.depth + 1,
            is_archived=is_archived,
            sort_order=sort_order,
        )


@dataclass(frozen=True, slots=True)
class DefaultCategoryChild:
    """Потомок корня дефолтного дерева: слаг и отображаемое имя."""

    slug: str
    name: str


@dataclass(frozen=True, slots=True)
class DefaultCategoryRoot:
    """Корень дефолтного дерева и его потомки первого уровня."""

    kind: CategoryKind
    slug: str
    name: str
    children: tuple[DefaultCategoryChild, ...] = ()


# Раздел 3.3, таблица «Дефолтный набор». Порядок перечисления задаёт
# `sort_order`: сквозной счётчик по порядку строк таблицы, включая потомков
# сразу после своего корня.
DEFAULT_CATEGORY_TREE: tuple[DefaultCategoryRoot, ...] = (
    DefaultCategoryRoot(
        kind=CategoryKind.EXPENSE,
        slug="food",
        name="Еда",
        children=(
            DefaultCategoryChild(slug="groceries", name="Продукты"),
            DefaultCategoryChild(slug="cafe", name="Кафе и рестораны"),
            DefaultCategoryChild(slug="coffee", name="Кофе"),
        ),
    ),
    DefaultCategoryRoot(
        kind=CategoryKind.EXPENSE,
        slug="transport",
        name="Транспорт",
        children=(
            DefaultCategoryChild(slug="public", name="Общественный транспорт"),
            DefaultCategoryChild(slug="taxi", name="Такси"),
            DefaultCategoryChild(slug="car", name="Автомобиль"),
        ),
    ),
    DefaultCategoryRoot(
        kind=CategoryKind.EXPENSE,
        slug="housing",
        name="Жильё",
        children=(
            DefaultCategoryChild(slug="rent", name="Аренда"),
            DefaultCategoryChild(slug="utilities", name="Коммунальные услуги"),
            DefaultCategoryChild(slug="internet", name="Связь и интернет"),
        ),
    ),
    DefaultCategoryRoot(
        kind=CategoryKind.EXPENSE,
        slug="health",
        name="Здоровье",
        children=(
            DefaultCategoryChild(slug="pharmacy", name="Аптека"),
            DefaultCategoryChild(slug="doctors", name="Врачи"),
        ),
    ),
    DefaultCategoryRoot(
        kind=CategoryKind.EXPENSE,
        slug="shopping",
        name="Покупки",
        children=(
            DefaultCategoryChild(slug="clothes", name="Одежда"),
            DefaultCategoryChild(slug="household", name="Товары для дома"),
            DefaultCategoryChild(slug="electronics", name="Техника"),
        ),
    ),
    DefaultCategoryRoot(
        kind=CategoryKind.EXPENSE,
        slug="leisure",
        name="Развлечения",
        children=(
            DefaultCategoryChild(slug="subscriptions", name="Подписки"),
            DefaultCategoryChild(slug="hobby", name="Хобби"),
            DefaultCategoryChild(slug="events", name="Мероприятия"),
        ),
    ),
    DefaultCategoryRoot(kind=CategoryKind.EXPENSE, slug="travel", name="Путешествия"),
    DefaultCategoryRoot(kind=CategoryKind.EXPENSE, slug="education", name="Образование"),
    DefaultCategoryRoot(kind=CategoryKind.EXPENSE, slug="gifts", name="Подарки"),
    DefaultCategoryRoot(kind=CategoryKind.EXPENSE, slug="misc", name="Прочие расходы"),
    DefaultCategoryRoot(kind=CategoryKind.INCOME, slug="salary", name="Зарплата"),
    DefaultCategoryRoot(kind=CategoryKind.INCOME, slug="bonus", name="Премии"),
    DefaultCategoryRoot(kind=CategoryKind.INCOME, slug="freelance", name="Подработка"),
    DefaultCategoryRoot(kind=CategoryKind.INCOME, slug="cashback", name="Кешбэк"),
    DefaultCategoryRoot(kind=CategoryKind.INCOME, slug="gifts_received", name="Подарки"),
    DefaultCategoryRoot(kind=CategoryKind.INCOME, slug="other_income", name="Прочие доходы"),
)


def build_default_categories(
    *,
    user_id: UUID,
    id_factory: Callable[[], UUID],
) -> list[Category]:
    """Строит копию `DEFAULT_CATEGORY_TREE` как список `Category` для `user_id`.

    Чистая функция: не обращается к IO, идентификаторы получает из
    `id_factory`, переданной вызывающей стороной (домен UUIDv7 не
    генерирует). Порядок результата совпадает с порядком таблицы «Дефолтный
    набор» — он же задаёт `sort_order`.
    """
    categories: list[Category] = []
    sort_order = 0
    for root_spec in DEFAULT_CATEGORY_TREE:
        root = Category.new_root(
            id=id_factory(),
            user_id=user_id,
            kind=root_spec.kind,
            slug=root_spec.slug,
            name=root_spec.name,
            sort_order=sort_order,
        )
        categories.append(root)
        sort_order += 1
        for child_spec in root_spec.children:
            categories.append(
                Category.new_child(
                    id=id_factory(),
                    parent=root,
                    slug=child_spec.slug,
                    name=child_spec.name,
                    sort_order=sort_order,
                )
            )
            sort_order += 1
    return categories


__all__ = (
    "DEFAULT_CATEGORY_TREE",
    "MAX_DEPTH",
    "SLUG_PATTERN",
    "Category",
    "CategoryKind",
    "DefaultCategoryChild",
    "DefaultCategoryRoot",
    "build_default_categories",
)
