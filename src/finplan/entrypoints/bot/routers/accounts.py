"""Роутер счетов: `/balance` и просмотр остатков.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `Command('balance')`,
`F.data.startswith('acc:')`. Хендлеры добавит подзадача 14 плана
`docs/tasks/2026-09-23-stage1-plan.md` поверх готового use case
`container.get_balances`.
"""

from __future__ import annotations

from aiogram import Router

router = Router(name="accounts")
