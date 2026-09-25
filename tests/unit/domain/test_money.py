"""Модульные тесты `Money`: арифметика и округление.

`docs/architecture.md`, раздел 3.1. Три приёма раздела 11.2:

- контрольные примеры (`test_rounding_boundary_examples_match_document`);
- сверка с эталоном — `Decimal.quantize` напрямую, в обход `Money`
  (`test_round_to_minor_unit_matches_manual_decimal_reference`);
- свойства через `hypothesis` (`Test*Hypothesis`).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from finplan.domain.common.currency import RUB, USD, Currency
from finplan.domain.common.errors import CurrencyMismatchError
from finplan.domain.common.money import Money

# ---------------------------------------------------------------------------
# Арифметика: сложение, вычитание, смешение валют
# ---------------------------------------------------------------------------


def test_addition_in_same_currency() -> None:
    total = Money(Decimal("10.50"), RUB) + Money(Decimal("4.25"), RUB)
    assert total == Money(Decimal("14.75"), RUB)


def test_subtraction_in_same_currency() -> None:
    result = Money(Decimal("10.50"), RUB) - Money(Decimal("4.25"), RUB)
    assert result == Money(Decimal("6.25"), RUB)


def test_addition_of_different_currencies_raises_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("10.00"), RUB) + Money(Decimal("10.00"), USD)


def test_subtraction_of_different_currencies_raises_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("10.00"), RUB) - Money(Decimal("10.00"), USD)


# ---------------------------------------------------------------------------
# Умножение и деление
# ---------------------------------------------------------------------------


def test_multiplication_by_decimal() -> None:
    result = Money(Decimal("3.00"), RUB) * Decimal("2.5")
    assert result == Money(Decimal("7.500"), RUB)


def test_multiplication_by_int() -> None:
    result = Money(Decimal("3.00"), RUB) * 3
    assert result == Money(Decimal("9.00"), RUB)


def test_reflected_multiplication_by_int() -> None:
    """`__rmul__`: `int * Money` работает так же, как `Money * int`."""
    result = 3 * Money(Decimal("3.00"), RUB)
    assert result == Money(Decimal("9.00"), RUB)


def test_multiplication_by_float_is_rejected() -> None:
    """Раздел 3.1: умножение допустимо только на `Decimal` или `int`."""
    with pytest.raises(TypeError):
        Money(Decimal("3.00"), RUB) * 2.5  # type: ignore[operator]


def test_division_by_money_returns_decimal_share() -> None:
    result = Money(Decimal("30.00"), RUB) / Money(Decimal("12.00"), RUB)
    assert result == Decimal("2.5")
    assert isinstance(result, Decimal)


def test_division_by_decimal_returns_decimal() -> None:
    result = Money(Decimal("30.00"), RUB) / Decimal("4")
    assert result == Decimal("7.5")
    assert isinstance(result, Decimal)


def test_division_by_money_in_different_currency_raises_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("30.00"), RUB) / Money(Decimal("12.00"), USD)


def test_division_by_float_is_rejected() -> None:
    with pytest.raises(TypeError):
        Money(Decimal("30.00"), RUB) / 2.5  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Конструктор и `Money.zero`
# ---------------------------------------------------------------------------


def test_constructor_rejects_float_amount() -> None:
    """Раздел 3.1: деньги — `Decimal`, никогда `float`."""
    with pytest.raises(TypeError):
        Money(1.5, RUB)  # type: ignore[arg-type]


def test_money_zero_has_zero_amount_in_given_currency() -> None:
    zero = Money.zero(USD)
    assert zero == Money(Decimal("0"), USD)


# ---------------------------------------------------------------------------
# Округление до минорной единицы: контрольные примеры раздела 3.1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("0.005"), Decimal("0.01")),
        (Decimal("-0.005"), Decimal("-0.01")),
        (Decimal("2.675"), Decimal("2.68")),
        (Decimal("2.674"), Decimal("2.67")),
        (Decimal("2.665"), Decimal("2.67")),
    ],
)
def test_rounding_boundary_examples_match_document(amount: Decimal, expected: Decimal) -> None:
    """Раздел 3.1: `ROUND_HALF_UP`, а не банковское округление.

    Контрольные значения — из задания, ровно на середине минорной единицы,
    где `ROUND_HALF_UP` и `ROUND_HALF_EVEN` расходятся.
    """
    rounded = Money(amount, RUB).round_to_minor_unit()
    assert rounded.amount == expected


def test_rounding_respects_currency_with_zero_minor_unit() -> None:
    jpy = Currency(code="JPY", minor_unit=0)
    rounded = Money(Decimal("2.5"), jpy).round_to_minor_unit()
    assert rounded.amount == Decimal("3")


@given(
    amount=st.decimals(
        min_value=Decimal("-1000000"),
        max_value=Decimal("1000000"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_round_to_minor_unit_matches_manual_decimal_reference(amount: Decimal) -> None:
    """Сверка с эталоном: округление `Money` совпадает с прямым
    `Decimal.quantize(..., ROUND_HALF_UP)`, посчитанным без участия `Money`."""
    reference = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rounded = Money(amount, RUB).round_to_minor_unit()
    assert rounded.amount == reference


# ---------------------------------------------------------------------------
# Свойства арифметики через hypothesis (раздел 11.1)
# ---------------------------------------------------------------------------

_money_amounts = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


@given(a=_money_amounts, b=_money_amounts, c=_money_amounts)
def test_addition_is_associative(a: Decimal, b: Decimal, c: Decimal) -> None:
    left = (Money(a, RUB) + Money(b, RUB)) + Money(c, RUB)
    right = Money(a, RUB) + (Money(b, RUB) + Money(c, RUB))
    assert left == right


@given(a=_money_amounts, b=_money_amounts)
def test_addition_and_subtraction_are_inverse(a: Decimal, b: Decimal) -> None:
    original = Money(a, RUB)
    result = (original + Money(b, RUB)) - Money(b, RUB)
    assert result == original


@given(a=_money_amounts)
def test_zero_is_the_additive_identity(a: Decimal) -> None:
    original = Money(a, RUB)
    assert original + Money.zero(RUB) == original
    assert Money.zero(RUB) + original == original
