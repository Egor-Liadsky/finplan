"""Value object `Currency`: код ISO 4217 и минорная единица.

`docs/architecture.md`, раздел 3.1, абзац «Валюты».
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from finplan.domain.common.errors import InvariantViolationError

_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Currency:
    """Код валюты ISO 4217 и число знаков минорной единицы.

    Неизменяем и сравним по значению: два `Currency` с одинаковым `code` и
    `minor_unit` равны, `frozen=True` запрещает менять поля после создания.
    """

    code: str
    minor_unit: int

    def __post_init__(self) -> None:
        if not _CODE_PATTERN.fullmatch(self.code):
            raise InvariantViolationError(
                f"код валюты должен быть тремя заглавными латинскими буквами: {self.code!r}"
            )
        if not 0 <= self.minor_unit <= 4:
            raise InvariantViolationError(f"minor_unit должен быть от 0 до 4: {self.minor_unit!r}")


RUB = Currency(code="RUB", minor_unit=2)
USD = Currency(code="USD", minor_unit=2)
EUR = Currency(code="EUR", minor_unit=2)
