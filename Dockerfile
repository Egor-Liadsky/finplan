# Единый образ для процессов api, bot и worker (docs/architecture.md,
# раздел 1.2 «Развёртываемые процессы»): один образ, одна версия доменного
# кода, процесс выбирается командой контейнера — не отдельным образом на
# каждую точку входа. Миграции здесь не запускаются, раздел 10.4 требует
# отдельного шага деплоя (сервис `migrate` в docker-compose.yml, а не
# `ENTRYPOINT`/`CMD` этого образа).

# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

# uv ставит зависимости из pyproject.toml и uv.lock без повторного
# разрешения версий (--frozen): состав окружения детерминирован тем же
# lock-файлом, что и локальная разработка.
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Слой зависимостей отделён от слоя исходников: пока pyproject.toml и
# uv.lock не меняются, повторная сборка после правки src/ переиспользует
# этот слой из кеша Docker и не переустанавливает зависимости.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Исходники и всё, что нужно для установки самого пакета finplan
# (hatchling читает README.md как readme проекта) и для запуска Alembic.
COPY README.md ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

WORKDIR /app

# Контейнер работает не от root.
RUN groupadd --system finplan \
    && useradd --system --gid finplan --home-dir /app --shell /usr/sbin/nologin finplan

COPY --from=builder --chown=finplan:finplan /app /app

ENV PATH="/app/.venv/bin:$PATH"

USER finplan

# Команда переопределяется в docker-compose.yml (раздел 10.3) для каждого
# процесса: uvicorn для api, `python -m finplan.entrypoints.bot.main` для
# bot, `python -m finplan.entrypoints.worker.main` для worker, одноразовая
# команда Alembic (раздел 10.4) для сервиса migrate. Значение по умолчанию —
# api, самый частый случай при сборке образа вручную.
CMD ["uvicorn", "finplan.entrypoints.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
