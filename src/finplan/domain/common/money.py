"""Value object `Money`: сумма и валюта, единая политика округления.

`docs/architecture.md`, раздел 3.1. Контекст округления объявлен один раз в
этом модуле и используется явно везде, где нужно округление до минорной
единицы — без опоры на глобальный контекст модуля `decimal`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Context, Decimal

from finplan.domain.common.currency import Currency
from finplan.domain.common.errors import CurrencyMismatchError

# Раздел 3.1: `ROUND_HALF_UP`, а не банковское `ROUND_HALF_EVEN`, — пользователь
# сверяет цифры с выпиской банка, где привычно арифметическое округление.
# `prec=28` — то же значение, что у контекста `decimal` по умолчанию,
# заявлено явно, чтобы не зависеть от глобальной настройки процесса.
MONEY_ROUNDING_CONTEXT = Context(prec=28, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class Money:
    """Сумма в конкретной валюте.

    Знак допустим в обе стороны (раздел 3.1, абзац «Арифметика», последнее
    предложение): направление движения денег задаёт `TransactionKind`, а не
    знак суммы — отрицательными законно бывают остаток счёта с овердрафтом и
    разность двух `Money`. Запрет отрицательной суммы операции — инвариант
    `Transaction`, а не `Money`.
    """

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError(f"amount должен быть Decimal, получено {self.amount!r}")

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        """Нулевая сумма в заданной валюте."""
        return cls(amount=Decimal(0), currency=currency)

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"несовпадение валют: {self.currency.code} и {other.currency.code}"
            )

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __neg__(self) -> Money:
        return Money(amount=-self.amount, currency=self.currency)

    def __mul__(self, factor: Decimal | int) -> Money:
        if not isinstance(factor, (Decimal, int)) or isinstance(factor, bool):
            raise TypeError(f"множитель должен быть Decimal или int, получено {factor!r}")
        return Money(amount=self.amount * Decimal(factor), currency=self.currency)

    __rmul__ = __mul__

    def __truediv__(self, divisor: Money | Decimal | int) -> Decimal:
        """Деление всегда возвращает `Decimal`, а не `Money` (раздел 3.1).

        Деление на `Money` той же валюты даёт безразмерную долю одной суммы
        от другой; деление на `Decimal`/`int` — пропорциональную величину
        суммы. Оба случая — числа, не денежные суммы, поэтому результат не
        `Money`.
        """
        if isinstance(divisor, Money):
            self._require_same_currency(divisor)
            return self.amount / divisor.amount
        if isinstance(divisor, (Decimal, int)) and not isinstance(divisor, bool):
            return self.amount / Decimal(divisor)
        raise TypeError(f"делитель должен быть Money, Decimal или int, получено {divisor!r}")

    def round_to_minor_unit(self) -> Money:
        """Округление `ROUND_HALF_UP` до минорной единицы валюты."""
        quantum = Decimal(1).scaleb(-self.currency.minor_unit, context=MONEY_ROUNDING_CONTEXT)
        rounded = self.amount.quantize(quantum, context=MONEY_ROUNDING_CONTEXT)
        return Money(amount=rounded, currency=self.currency)
