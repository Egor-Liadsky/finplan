"""Базовая модель DTO для слоя `application`.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»: DTO — модели pydantic с `frozen=True`, `strict=True` и
`extra="forbid"`; деньги — `Decimal` с кодом валюты строкой, `Money` в
DTO не попадает, а строгий режим не даёт нецелочисленному числу с плавающей
точкой превратиться в `Decimal` молча.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Dto(BaseModel):
    """Базовая неизменяемая модель DTO в строгом режиме pydantic."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
