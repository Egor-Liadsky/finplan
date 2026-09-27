"""Форматирование денежных сумм для сообщений бота.

`docs/architecture.md`, раздел 3.1 (округление `ROUND_HALF_UP`, минорные
единицы валюты) и раздел 6.5 (карточка подтверждения показывает суммы в
привычном пользователю виде).
"""

from __future__ import annotations

from decimal import Decimal

from finplan.domain.common.currency import EUR, RUB, USD, Currency
from finplan.domain.common.money import MONEY_ROUNDING_CONTEXT

_KNOWN_CURRENCIES: dict[str, Currency] = {c.code: c for c in (RUB, USD, EUR)}
_CODE_TO_SYMBOL: dict[str, str] = {"RUB": "₽", "USD": "$", "EUR": "€"}
_DEFAULT_MINOR_UNIT = 2
_THIN_SPACE = " "


def format_money(amount: Decimal, currency_code: str) -> str:
    """Форматирует сумму: разряды через неразрывный пробел, дробь через запятую.

    Дробная часть показывается с `minor_unit` знаками валюты, если она есть
    в справочнике доменных констант, иначе с двумя. Нулевая дробная часть
    опускается. Округление — `ROUND_HALF_UP`. Для `RUB`, `USD`, `EUR` после
    суммы ставится символ, для остальных валют — код.
    """
    currency = _KNOWN_CURRENCIES.get(currency_code)
    minor_unit = currency.minor_unit if currency is not None else _DEFAULT_MINOR_UNIT

    quantum = Decimal(1).scaleb(-minor_unit, context=MONEY_ROUNDING_CONTEXT)
    rounded = amount.copy_abs().quantize(quantum, context=MONEY_ROUNDING_CONTEXT)
    sign = "-" if amount < 0 else ""

    int_part, _, frac_part = format(rounded, "f").partition(".")
    text = _group_thousands(int_part)
    if frac_part and int(frac_part) != 0:
        text = f"{text},{frac_part}"

    tail = _CODE_TO_SYMBOL.get(currency_code, currency_code)
    return f"{sign}{text} {tail}"


def _group_thousands(digits: str) -> str:
    groups: list[str] = []
    for end in range(len(digits), 0, -3):
        start = max(end - 3, 0)
        groups.append(digits[start:end])
    return _THIN_SPACE.join(reversed(groups))
