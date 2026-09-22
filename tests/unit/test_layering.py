"""Проверка направления зависимостей по `docs/architecture.md`, раздел 2.2.

Модульный тест: обходит `src/finplan/**/*.py`, разбирает импорты через `ast`
(`Import` и `ImportFrom`, включая относительные, приведённые к абсолютному
виду) и проверяет, что нижний слой не импортирует верхний и не тянет чужие
инфраструктурные библиотеки. Проверка текстом строк (`grep`) сюда не
годится: закомментированный импорт или совпадение подстроки в докстроке дали
бы ложное срабатывание или ложный пропуск, а разбор через `ast` видит только
настоящие узлы импорта.

Второй тест (`test_analyzer_detects_synthetic_violation`) проверяет сам
анализатор на искусственном фрагменте с заведомым нарушением: зелёный
результат первого теста иначе не отличить от анализатора, который просто
ничего не видит.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

# Раздел 2.2 дословно: домен не видит верхние слои и инфраструктурные
# библиотеки, application не видит infrastructure/entrypoints и веб/БД
# библиотеки, infrastructure не видит entrypoints.
LAYER_RULES: dict[str, tuple[str, ...]] = {
    "finplan.domain": (
        "finplan.application",
        "finplan.infrastructure",
        "finplan.entrypoints",
        "sqlalchemy",
        "aiogram",
        "fastapi",
        "pydantic_settings",
        "redis",
        "asyncpg",
        "alembic",
    ),
    "finplan.application": (
        "finplan.infrastructure",
        "finplan.entrypoints",
        "sqlalchemy",
        "aiogram",
        "fastapi",
    ),
    "finplan.infrastructure": ("finplan.entrypoints",),
}


@dataclass(frozen=True, slots=True)
class ImportViolation:
    """Один запрещённый импорт, найденный анализатором."""

    file: Path
    line: int
    imported: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: запрещённый импорт {self.imported!r}"


def _module_dotted_name(file_path: Path, src_root: Path) -> str:
    """Путь файла относительно `src_root` -> точечное имя модуля."""
    relative = file_path.relative_to(src_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package_of(dotted_module: str, is_package: bool) -> str:
    """Пакет, относительно которого разрешаются относительные импорты модуля.

    Для `__init__.py` пакета `__package__` совпадает с именем самого пакета;
    для обычного модуля — это имя родительского пакета (всё, кроме
    последнего компонента).
    """
    if is_package:
        return dotted_module
    if "." not in dotted_module:
        return ""
    return dotted_module.rsplit(".", 1)[0]


def _resolve_relative(package: str, level: int, module: str | None) -> str:
    """Приводит относительный импорт (`level` точек) к абсолютному имени."""
    bits = package.split(".") if package else []
    if level > 1:
        extra_up = level - 1
        bits = bits[:-extra_up] if len(bits) >= extra_up else []
    base = ".".join(bits)
    if module:
        return f"{base}.{module}" if base else module
    return base


def _collect_imports(source: str, dotted_module: str, is_package: bool) -> list[tuple[int, str]]:
    """Возвращает пары (номер строки, точечное имя импортируемого модуля)."""
    tree = ast.parse(source)
    package = _package_of(dotted_module, is_package)
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                resolved_module = node.module or ""
            else:
                resolved_module = _resolve_relative(package, node.level, node.module)
            if resolved_module:
                imports.append((node.lineno, resolved_module))
            for alias in node.names:
                if alias.name == "*":
                    continue
                combined = f"{resolved_module}.{alias.name}" if resolved_module else alias.name
                imports.append((node.lineno, combined))
    return imports


def _matches(imported: str, disallowed_prefix: str) -> bool:
    """`imported` — это сам `disallowed_prefix` или что-то внутри него."""
    return imported == disallowed_prefix or imported.startswith(disallowed_prefix + ".")


def find_violations(src_root: Path) -> list[ImportViolation]:
    """Обходит все `*.py` под `src_root` и собирает нарушения раздела 2.2."""
    violations: list[ImportViolation] = []
    for file_path in sorted(src_root.rglob("*.py")):
        dotted = _module_dotted_name(file_path, src_root)
        is_package = file_path.name == "__init__.py"
        for layer_prefix, disallowed in LAYER_RULES.items():
            if not (dotted == layer_prefix or dotted.startswith(layer_prefix + ".")):
                continue
            source = file_path.read_text(encoding="utf-8")
            for lineno, imported in _collect_imports(source, dotted, is_package):
                for bad_prefix in disallowed:
                    if _matches(imported, bad_prefix):
                        violations.append(ImportViolation(file_path, lineno, imported))
            break  # модуль принадлежит ровно одному из перечисленных слоёв
    return violations


def test_layers_do_not_violate_dependency_direction() -> None:
    """Ни один файл `src/finplan/**` не нарушает правила слоёв раздела 2.2."""
    violations = find_violations(SRC_ROOT)
    if violations:
        details = "\n".join(str(violation) for violation in violations)
        pytest.fail(f"нарушение правил слоёв (docs/architecture.md, раздел 2.2):\n{details}")


def test_analyzer_detects_synthetic_violation(tmp_path: Path) -> None:
    """Самопроверка анализатора: на заведомо неверном коде он обязан упасть.

    Без этого теста зелёный результат `test_layers_do_not_violate_dependency_direction`
    неотличим от анализатора, который ничего не проверяет.
    """
    fake_src = tmp_path / "src"
    domain_dir = fake_src / "finplan" / "domain"
    domain_dir.mkdir(parents=True)
    (fake_src / "finplan" / "__init__.py").write_text("", encoding="utf-8")
    (domain_dir / "__init__.py").write_text("", encoding="utf-8")
    (domain_dir / "bad.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import sqlalchemy\n"
        "from finplan.application.use_cases.accounts import create_account\n"
        "from .. import application as sibling\n",
        encoding="utf-8",
    )

    violations = find_violations(fake_src)

    imported_names = {violation.imported for violation in violations}
    assert any(name == "sqlalchemy" for name in imported_names)
    assert any(name.startswith("finplan.application") for name in imported_names)
    assert len(violations) >= 3


def test_analyzer_passes_clean_synthetic_code(tmp_path: Path) -> None:
    """Контрольный отрицательный пример: разрешённый код не даёт нарушений."""
    fake_src = tmp_path / "src"
    domain_dir = fake_src / "finplan" / "domain" / "finance"
    domain_dir.mkdir(parents=True)
    (fake_src / "finplan" / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "finplan" / "domain" / "__init__.py").write_text("", encoding="utf-8")
    (domain_dir / "__init__.py").write_text("", encoding="utf-8")
    (domain_dir / "money.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "from decimal import Decimal\n"
        "\n"
        "from finplan.domain.common.errors import CurrencyMismatchError\n",
        encoding="utf-8",
    )

    assert find_violations(fake_src) == []
