"""Роутер диалога добавления расхода.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `Command('expense')`,
`F.data.startswith('exp:')`, `StateFilter(AddExpense)`. Хендлеры диалога
добавит подзадача 13 плана `docs/tasks/2026-09-23-stage1-plan.md`.
"""

from __future__ import annotations

from aiogram import Router

router = Router(name="expense")
