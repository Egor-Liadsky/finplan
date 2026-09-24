"""Модульные тесты `Category` и `build_default_categories`.

`docs/architecture.md`, раздел 3.3, таблица `Category`, абзацы про слаги и
про дефолтный набор.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from finplan.domain.common.errors import InvariantViolationError
from finplan.domain.entities.category import (
    MAX_DEPTH,
    Category,
    CategoryKind,
    build_default_categories,
)

# ---------------------------------------------------------------------------
# Правило слагов `path`: `^[a-z][a-z0-9_]*$`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", ["food", "food_2", "a", "coffee_and_tea"])
def test_valid_root_slug_is_accepted(slug: str) -> None:
    category = Category.new_root(
        id=uuid4(), user_id=uuid4(), kind=CategoryKind.EXPENSE, slug=slug, name="Категория"
    )
    assert category.path == slug


@pytest.mark.parametrize(
    "slug",
    ["Food", "2food", "food-bar", "food bar", "", "食品", "_food"],
)
def test_invalid_root_slug_is_rejected(slug: str) -> None:
    with pytest.raises(InvariantViolationError):
        Category.new_root(
            id=uuid4(), user_id=uuid4(), kind=CategoryKind.EXPENSE, slug=slug, name="Категория"
        )


# ---------------------------------------------------------------------------
# Ограничение глубины: три уровня, `depth` от 0 до `MAX_DEPTH` (2)
# ---------------------------------------------------------------------------


def test_default_max_depth_is_two() -> None:
    """Раздел 3.3: глубина набора — три уровня (`depth` 0, 1, 2)."""
    assert MAX_DEPTH == 2


def test_third_level_child_is_accepted_at_the_depth_boundary() -> None:
    root = Category.new_root(
        id=uuid4(), user_id=uuid4(), kind=CategoryKind.EXPENSE, slug="food", name="Еда"
    )
    child = Category.new_child(id=uuid4(), parent=root, slug="coffee", name="Кофе")
    grandchild = Category.new_child(id=uuid4(), parent=child, slug="black", name="Чёрный кофе")
    assert grandchild.depth == MAX_DEPTH
    assert grandchild.path == "food.coffee.black"


def test_child_of_max_depth_category_is_rejected() -> None:
    root = Category.new_root(
        id=uuid4(), user_id=uuid4(), kind=CategoryKind.EXPENSE, slug="food", name="Еда"
    )
    child = Category.new_child(id=uuid4(), parent=root, slug="coffee", name="Кофе")
    grandchild = Category.new_child(id=uuid4(), parent=child, slug="black", name="Чёрный кофе")
    with pytest.raises(InvariantViolationError):
        Category.new_child(id=uuid4(), parent=grandchild, slug="latte", name="Латте")


def test_direct_construction_with_depth_out_of_range_is_rejected() -> None:
    with pytest.raises(InvariantViolationError):
        Category(
            id=uuid4(),
            user_id=uuid4(),
            parent_id=uuid4(),
            kind=CategoryKind.EXPENSE,
            name="Слишком глубоко",
            path="food.coffee.black.latte",
            depth=3,
        )


def test_path_must_match_declared_depth() -> None:
    with pytest.raises(InvariantViolationError):
        Category(
            id=uuid4(),
            user_id=uuid4(),
            parent_id=None,
            kind=CategoryKind.EXPENSE,
            name="Некорректный путь",
            path="food.coffee",
            depth=0,
        )


def test_root_category_forbids_parent_id() -> None:
    with pytest.raises(InvariantViolationError):
        Category(
            id=uuid4(),
            user_id=uuid4(),
            parent_id=uuid4(),
            kind=CategoryKind.EXPENSE,
            name="Еда",
            path="food",
            depth=0,
        )


def test_non_root_category_requires_parent_id() -> None:
    with pytest.raises(InvariantViolationError):
        Category(
            id=uuid4(),
            user_id=uuid4(),
            parent_id=None,
            kind=CategoryKind.EXPENSE,
            name="Кофе",
            path="food.coffee",
            depth=1,
        )


def test_child_inherits_kind_from_parent() -> None:
    """Раздел 3.3: `kind` дочерней категории совпадает с `kind` родителя."""
    root = Category.new_root(
        id=uuid4(), user_id=uuid4(), kind=CategoryKind.INCOME, slug="salary", name="Зарплата"
    )
    child = Category.new_child(id=uuid4(), parent=root, slug="bonus_part", name="Премиальная часть")
    assert child.kind is CategoryKind.INCOME


# ---------------------------------------------------------------------------
# Алиасы: нормализованные слова без повторов (раздел 3.3)
# ---------------------------------------------------------------------------


def _root_with_aliases(aliases: tuple[str, ...]) -> Category:
    return Category(
        id=uuid4(),
        user_id=uuid4(),
        parent_id=None,
        kind=CategoryKind.EXPENSE,
        name="Кофе",
        path="coffee",
        depth=0,
        aliases=aliases,
    )


def test_category_has_no_aliases_by_default() -> None:
    root = Category.new_root(
        id=uuid4(), user_id=uuid4(), kind=CategoryKind.EXPENSE, slug="food", name="Еда"
    )
    assert root.aliases == ()


def test_normalized_aliases_are_accepted() -> None:
    assert _root_with_aliases(("кофе", "латте")).aliases == ("кофе", "латте")


@pytest.mark.parametrize("alias", ["", "Кофе", " кофе", "кофе "])
def test_not_normalized_alias_is_rejected(alias: str) -> None:
    with pytest.raises(InvariantViolationError):
        _root_with_aliases((alias,))


def test_duplicate_aliases_are_rejected() -> None:
    with pytest.raises(InvariantViolationError):
        _root_with_aliases(("кофе", "кофе"))


# ---------------------------------------------------------------------------
# Дефолтное дерево категорий
# ---------------------------------------------------------------------------


def _id_factory() -> UUID:
    return uuid4()


def test_default_categories_total_count_matches_document() -> None:
    """Раздел 3.3, таблица «Дефолтный набор»: 27 расходных и 6 доходных."""
    user_id = uuid4()
    categories = build_default_categories(user_id=user_id, id_factory=_id_factory)
    assert len(categories) == 33
    expense = [c for c in categories if c.kind is CategoryKind.EXPENSE]
    income = [c for c in categories if c.kind is CategoryKind.INCOME]
    assert len(expense) == 27
    assert len(income) == 6


def test_default_categories_all_belong_to_the_same_user() -> None:
    user_id = uuid4()
    categories = build_default_categories(user_id=user_id, id_factory=_id_factory)
    assert all(category.user_id == user_id for category in categories)


def test_default_categories_have_unique_paths() -> None:
    categories = build_default_categories(user_id=uuid4(), id_factory=_id_factory)
    paths = [category.path for category in categories]
    assert len(paths) == len(set(paths))


def test_default_categories_children_have_parent_in_the_set_with_same_kind() -> None:
    categories = build_default_categories(user_id=uuid4(), id_factory=_id_factory)
    by_id = {category.id: category for category in categories}
    children = [category for category in categories if category.parent_id is not None]
    assert children, "в дефолтном наборе есть дочерние категории"
    for child in children:
        parent = by_id.get(child.parent_id)  # type: ignore[arg-type]
        assert parent is not None, f"родитель {child.parent_id} потомка {child.path} не найден"
        assert parent.kind == child.kind


def test_default_categories_sort_order_matches_enumeration_order() -> None:
    """Раздел 3.3: порядок перечисления таблицы задаёт `sort_order`."""
    categories = build_default_categories(user_id=uuid4(), id_factory=_id_factory)
    sort_orders = [category.sort_order for category in categories]
    assert sort_orders == list(range(len(categories)))
