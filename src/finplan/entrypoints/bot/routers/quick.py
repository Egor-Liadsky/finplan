"""Роутер быстрого ввода одной строкой.

`docs/architecture.md`, раздел 6.2, таблица роутеров: `F.text &
~F.text.startswith('/')`, `StateFilter(None)`, всегда последний в цепочке,
чтобы не перехватывать текст, ожидаемый диалогом. Хендлер добавит
подзадача 13 плана `docs/tasks/2026-09-23-stage1-plan.md` поверх парсера
`parsers/quickinput.py`.
"""

from __future__ import annotations

from aiogram import Router

router = Router(name="quick")
