"""Ошибки сценариев слоя application.

`docs/architecture.md`, раздел 2.2, абзац «Контракт портов и граница
транзакции»: отказ сценария, который не является нарушением доменного
инварианта, use case сообщает этими исключениями. `DomainError` из домена
проходит наверх без обёртки.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Базовое исключение сценария. Любая ошибка use case — его потомок."""


class NotFoundError(ApplicationError):
    """Пользователь, счёт или категория не найдены у `user_id` либо архивированы."""


class InvalidCommandError(ApplicationError):
    """Команда противоречит данным: например, категория не того вида."""
