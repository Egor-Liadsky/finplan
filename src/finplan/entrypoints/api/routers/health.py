"""Эндпоинт ``GET /health``.

Раздел `docs/architecture.md`, 13 «Этап 0»: точка входа `api` отвечает на
health-check. Эндпоинт не требует аутентификации и не входит в префикс
`/api/v1` — соответствует тому, что в разделе 7.1 `/health` не перечислен
среди эндпоинтов SPA. Бизнес-логики нет: только чтение состояния engine из
`app.state` и один пробный запрос ``SELECT 1``.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()

APP_VERSION = version("finplan")


async def _check_database(request: Request) -> bool:
    """Выполняет ``SELECT 1`` через engine, сохранённый в ``app.state`` при старте."""
    engine = request.app.state.engine
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """Возвращает состояние приложения и результат проверки БД.

    ``200`` при успешной проверке БД, ``503`` с тем же телом и признаком
    неудачи (``database.ok is False``), если база недоступна.
    """
    database_ok = await _check_database(request)
    body: dict[str, Any] = {
        "status": "ok" if database_ok else "unavailable",
        "version": APP_VERSION,
        "database": {"ok": database_ok},
    }
    return JSONResponse(content=body, status_code=200 if database_ok else 503)
