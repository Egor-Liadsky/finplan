"""Роутер `/undo` — сторно последней операции, введённой в боте.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `Command('undo')`.
Хендлеры добавит подзадача 14 плана `docs/tasks/2026-09-23-stage1-plan.md`
поверх готового use case `container.undo_last`.
"""

from __future__ import annotations

from aiogram import Router

router = Router(name="undo")
