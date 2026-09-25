"""Парсер быстрого ввода одной строкой.

`docs/architecture.md`, раздел 6.5 (грамматика `[знак] сумма [валюта]
[текст] [#категория] [@счёт] [!дата]`) и раздел 6.6, абзац «Граница между
парсером и хендлером»: парсер — чистая функция от строки и сегодняшней даты
в таймзоне пользователя. Он не знает о счетах, категориях и базе, поэтому
проверяет только то, что видно из самой строки: сумма разбирается в
`Decimal` и лежит в `(0, 1e12)`, дата синтаксически корректна, комментарий
не длиннее 500 символов. Сумма возвращается без округления — округление до
`minor_unit` валюты счёта делает хендлер после разрешения счёта.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from finplan.domain.common.currency import EUR, RUB, USD, Currency
from finplan.domain.entities.transaction import TransactionKind

#: Раздел 3.1: доменные константы валют — единственный справочник, доступный
#: парсеру без обращения к базе.
_KNOWN_CURRENCIES: dict[str, Currency] = {c.code: c for c in (RUB, USD, EUR)}
_SYMBOL_TO_CODE: dict[str, str] = {"₽": "RUB", "$": "USD", "€": "EUR"}

_AMOUNT_UPPER_BOUND = Decimal("1e12")
_MAX_COMMENT_LENGTH = 500

_AMOUNT_RE = re.compile(
    r"^(?P<sign>[+-])?"
    r"(?P<presym>[₽$€])?"
    r"(?P<int>\d{1,3}(?: \d{3})+|\d+)"
    r"(?:[.,](?P<frac>\d+))?"
    r"(?P<suffix>[kKкК])?"
    r"(?P<postsym>[₽$€])?"
    # Сумма кончается пробелом или концом строки: иначе «1 2000» разобралось
    # бы как 1200 с комментарием «0», а «3kg» — как 3000 с комментарием «g».
    r"(?=\s|$)"
)
_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$")


class QuickInputErrorCode(StrEnum):
    """Коды ошибок разбора. Тексты к ним лежат в `formatters/errors.py`."""

    INVALID_AMOUNT = "invalid_amount"
    AMOUNT_OUT_OF_RANGE = "amount_out_of_range"
    EMPTY_MARKER = "empty_marker"
    DUPLICATE_MARKER = "duplicate_marker"
    INVALID_DATE = "invalid_date"


class QuickInputWarning(StrEnum):
    """Предупреждения, которые парсер кладёт в `QuickInput.warnings`."""

    COMMENT_TRUNCATED = "comment_truncated"


class QuickInputError(Exception):
    """Ошибка разбора строки быстрого ввода."""

    def __init__(self, code: QuickInputErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class QuickInput:
    """Результат разбора строки быстрого ввода."""

    kind: TransactionKind
    amount: Decimal
    currency_code: str | None
    comment: str | None
    category_ref: str | None
    account_ref: str | None
    occurred_on: date | None
    warnings: tuple[QuickInputWarning, ...]


def parse_quick_input(text: str, *, today: date) -> QuickInput:
    """Разбирает строку быстрого ввода по грамматике раздела 6.5."""
    stripped = text.strip()
    match = _AMOUNT_RE.match(stripped)
    if match is None:
        raise QuickInputError(QuickInputErrorCode.INVALID_AMOUNT)

    kind = TransactionKind.INCOME if match.group("sign") == "+" else TransactionKind.EXPENSE
    amount = _parse_amount(match)
    if not (Decimal(0) < amount < _AMOUNT_UPPER_BOUND):
        raise QuickInputError(QuickInputErrorCode.AMOUNT_OUT_OF_RANGE)

    currency_code = _currency_from_symbol(match.group("presym") or match.group("postsym"))
    tokens = stripped[match.end() :].split()

    if currency_code is None and tokens:
        detected, remaining = _take_currency_token(tokens)
        if detected is not None:
            currency_code = detected
            tokens = remaining

    category_ref, account_ref, occurred_on, comment_words = _extract_markers(tokens, today=today)

    warnings: list[QuickInputWarning] = []
    comment = " ".join(comment_words) or None
    if comment is not None and len(comment) > _MAX_COMMENT_LENGTH:
        comment = comment[:_MAX_COMMENT_LENGTH]
        warnings.append(QuickInputWarning.COMMENT_TRUNCATED)

    return QuickInput(
        kind=kind,
        amount=amount,
        currency_code=currency_code,
        comment=comment,
        category_ref=category_ref,
        account_ref=account_ref,
        occurred_on=occurred_on,
        warnings=tuple(warnings),
    )


def parse_amount(text: str) -> Decimal:
    """Разбирает сумму без знака, валюты и комментария — вся строка одна сумма.

    Тот же синтаксис суммы, что в `parse_quick_input` (раздел 6.5: разделитель
    `.` или `,`, пробелы-разделители тысяч, суффиксы `k`/`к`), и те же
    проверки диапазона с теми же кодами `QuickInputError`. Использует шаг
    `opening_balance` онбординга (раздел 6.3) и шаг суммы диалогов расхода и
    дохода.
    """
    stripped = text.strip()
    match = _AMOUNT_RE.match(stripped)
    has_sign_or_currency = match is not None and (
        match.group("sign") or match.group("presym") or match.group("postsym")
    )
    if match is None or match.end() != len(stripped) or has_sign_or_currency:
        raise QuickInputError(QuickInputErrorCode.INVALID_AMOUNT)
    amount = _parse_amount(match)
    if not (Decimal(0) < amount < _AMOUNT_UPPER_BOUND):
        raise QuickInputError(QuickInputErrorCode.AMOUNT_OUT_OF_RANGE)
    return amount


def _parse_amount(match: re.Match[str]) -> Decimal:
    int_part = match.group("int").replace(" ", "")
    frac_part = match.group("frac")
    raw = int_part if frac_part is None else f"{int_part}.{frac_part}"
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise QuickInputError(QuickInputErrorCode.INVALID_AMOUNT) from exc
    if match.group("suffix"):
        amount *= 1000
    return amount


def _currency_from_symbol(symbol: str | None) -> str | None:
    if symbol is None:
        return None
    return _SYMBOL_TO_CODE.get(symbol)


def _take_currency_token(tokens: list[str]) -> tuple[str | None, list[str]]:
    first = tokens[0]
    upper = first.upper()
    if upper in _KNOWN_CURRENCIES:
        return upper, tokens[1:]
    if first in _SYMBOL_TO_CODE:
        return _SYMBOL_TO_CODE[first], tokens[1:]
    return None, tokens


def _extract_markers(
    tokens: list[str], *, today: date
) -> tuple[str | None, str | None, date | None, list[str]]:
    category_ref: str | None = None
    account_ref: str | None = None
    date_token: str | None = None
    seen_markers: set[str] = set()
    comment_words: list[str] = []

    for token in tokens:
        marker = token[0] if token[:1] in ("#", "@", "!") else None
        if marker is None:
            comment_words.append(token)
            continue
        if marker in seen_markers:
            raise QuickInputError(QuickInputErrorCode.DUPLICATE_MARKER)
        seen_markers.add(marker)
        body = token[1:]
        if not body:
            raise QuickInputError(QuickInputErrorCode.EMPTY_MARKER)
        if marker == "#":
            category_ref = body
        elif marker == "@":
            account_ref = body
        else:
            date_token = body

    occurred_on = _parse_date_marker(date_token, today=today) if date_token is not None else None
    return category_ref, account_ref, occurred_on, comment_words


def _parse_date_marker(value: str, *, today: date) -> date:
    if value.lower() == "вчера":
        return today - timedelta(days=1)
    match = _DATE_RE.fullmatch(value)
    if match is None:
        raise QuickInputError(QuickInputErrorCode.INVALID_DATE)
    day_str, month_str, year_str = match.groups()
    year = int(year_str) if year_str is not None else today.year
    try:
        return date(year, int(month_str), int(day_str))
    except ValueError as exc:
        raise QuickInputError(QuickInputErrorCode.INVALID_DATE) from exc
