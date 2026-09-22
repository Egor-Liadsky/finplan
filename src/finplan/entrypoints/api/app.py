"""Сборка FastAPI-приложения `api`.

Раздел `docs/architecture.md`, 1.2 «Развёртываемые процессы», 10.4
«Миграции при старте», 12.1 «Логирование». Этап 0 даёт только каркас:
`lifespan`, CORS, middleware `request_id` и `GET /health`; use case и
доменная логика в этом слое не появляются.

`uvicorn finplan.entrypoints.api.app:app` (раздел 10.3) запускает модульный
объект `app`, собранный фабрикой :func:`create_app`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from ulid import ULID

from finplan.config import Settings, get_settings
from finplan.entrypoints.api.routers.health import router as health_router
from finplan.infrastructure.db.engine import create_engine
from finplan.infrastructure.db.revision import check_revision
from finplan.logging import bind_context, clear_context, configure_logging, get_logger

REQUEST_ID_HEADER = "X-Request-Id"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Настраивает логирование, поднимает engine и проверяет ревизию Alembic.

    По разделу 10.4 миграции при старте **не применяются** — только
    сравнение текущей ревизии `alembic_version` с `head` из кода. При
    расхождении `check_revision` поднимает `RevisionMismatchError` с обеими
    ревизиями в сообщении, и процесс не стартует.
    """
    settings: Settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)
    logger.info("process.starting", service="api", telegram_mode=settings.telegram.mode)

    engine = create_engine(settings.database)
    app.state.engine = engine
    app.state.settings = settings
    try:
        async with engine.connect() as connection:
            revision_status = await check_revision(connection)
        logger.info("api.revision_ok", revision=revision_status.head_revision)
        yield
    finally:
        await engine.dispose()
        logger.info("process.stopped", service="api")


def create_app() -> FastAPI:
    """Собирает `FastAPI`-приложение: `lifespan`, CORS, `request_id`, `/health`."""
    settings = get_settings()

    app = FastAPI(
        lifespan=lifespan,
        docs_url="/docs" if settings.app.debug else None,
        redoc_url="/redoc" if settings.app.debug else None,
        openapi_url="/openapi.json" if settings.app.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Проставляет `request_id` из заголовка или генерирует новый (раздел 12.1)."""
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(ULID())
        bind_context(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            clear_context()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    app.include_router(health_router)

    return app


app = create_app()
