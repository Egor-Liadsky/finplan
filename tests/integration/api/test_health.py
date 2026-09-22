"""`GET /health` через `httpx.ASGITransport` на реально собранном приложении.

Раздел `docs/architecture.md`, 13 «Этап 0»: эндпоинт отвечает `200`, тело
содержит признак успешной проверки БД, заголовок ``X-Request-Id`` (раздел
12.1) возвращается и совпадает с переданным, если он был передан.

`create_app()` вызывается заново в каждом тесте, а не переиспользуется
модульный объект `app` из `finplan.entrypoints.api.app` — тот собирается
один раз при самом импорте модуля, ещё до того как фикстура `env_vars`
подставит строку подключения к смигрированному контейнеру.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

pytestmark = pytest.mark.integration

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


@pytest_asyncio.fixture
async def api_app(env_vars: dict[str, str]) -> AsyncIterator[FastAPI]:
    """Приложение, собранное `create_app()` с рабочим `lifespan` (раздел 10.4)."""
    from finplan.entrypoints.api.app import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        yield app


@pytest_asyncio.fixture
async def client(api_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def test_health_returns_200_with_successful_db_check(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["ok"] is True


async def test_health_generates_ulid_request_id_when_absent(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    request_id = response.headers["X-Request-Id"]
    assert _ULID_RE.match(request_id), (
        f"{request_id!r} не похож на ULID (Crockford Base32, 26 симв.)"
    )


async def test_health_echoes_supplied_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-Id": "my-request-42"})

    assert response.headers["X-Request-Id"] == "my-request-42"
