"""Базовые доменные исключения.

Чистый Python: домен сигнализирует о нарушениях правил собственными
исключениями, а не кодами ошибок HTTP или SQLSTATE — это дело верхних слоёв
(`docs/architecture.md`, раздел 2.2 и раздел 7.4 про формат ошибок API).
"""

from __future__ import annotations


class DomainError(Exception):
    """Базовое исключение домена. Любая доменная ошибка — его потомок."""


class CurrencyMismatchError(DomainError):
    """Операция над `Money` в разных валютах (раздел 3.1: арифметика)."""


class InvariantViolationError(DomainError):
    """Нарушен инвариант сущности или value object (раздел 3.3)."""


class AlreadyReversedError(DomainError):
    """Повторное сторно операции, которая уже не в `posted` (раздел 3.3)."""
