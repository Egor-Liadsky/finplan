"""Роутер коротких отчётов: `/today`, `/month`.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `Command('today')`,
`Command('month')`, `F.data.startswith('rep:')`. Хендлеры добавит
подзадача 14 плана `docs/tasks/2026-09-23-stage1-plan.md` поверх готового
use case `container.period_summary`.
"""

from __future__ import annotations

from aiogram import Router

router = Router(name="reports")
