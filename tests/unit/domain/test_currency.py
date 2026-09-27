"""Модульные тесты `Currency`.

`docs/architecture.md`, раздел 3.1, абзац «Валюты»: код ISO 4217 — три
заглавные латинские буквы, `minor_unit` описывает число знаков минорной
единицы (2 у RUB/USD/EUR, 0 у JPY).
"""

from __future__ import annotations

import pytest

from finplan.domain.common.currency import EUR, RUB, USD, Currency
from finplan.domain.common.errors import InvariantViolationError


def test_known_currencies_have_documented_minor_units() -> None:
    """Раздел 3.1: RUB, USD, EUR — минорная единица 2 (копейки/центы)."""
    assert RUB == Currency(code="RUB", minor_unit=2)
    assert USD == Currency(code="USD", minor_unit=2)
    assert EUR == Currency(code="EUR", minor_unit=2)


def test_zero_minor_unit_currency_is_accepted() -> None:
    """Раздел 3.1: у JPY минорная единица 0 — граница диапазона снизу."""
    jpy = Currency(code="JPY", minor_unit=0)
    assert jpy.minor_unit == 0


@pytest.mark.parametrize(
    "code",
    ["rub", "Rub", "RU", "RUBL", "RU1", "", "РУБ"],
)
def test_invalid_iso_code_is_rejected(code: str) -> None:
    """Код обязан быть тремя заглавными латинскими буквами (раздел 3.1)."""
    with pytest.raises(InvariantViolationError):
        Currency(code=code, minor_unit=2)


@pytest.mark.parametrize("minor_unit", [-1, 5])
def test_minor_unit_out_of_range_is_rejected(minor_unit: int) -> None:
    """Диапазон `minor_unit` — от 0 до 4 включительно (раздел 3.1: хранение
    с точностью в 4 знака покрывает минорную единицу любой валюты)."""
    with pytest.raises(InvariantViolationError):
        Currency(code="RUB", minor_unit=minor_unit)


@pytest.mark.parametrize("minor_unit", [0, 4])
def test_minor_unit_boundary_values_are_accepted(minor_unit: int) -> None:
    currency = Currency(code="XTS", minor_unit=minor_unit)
    assert currency.minor_unit == minor_unit
