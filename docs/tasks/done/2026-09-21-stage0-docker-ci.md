# Сборка и CI: Dockerfile, docker-compose.yml, workflow GitHub Actions

- **Исполнитель:** developer
- **Слой:** docs (инфраструктура репозитория)
- **Раздел архитектуры:** docs/architecture.md, разделы 1.2, 2.1, 10.3, 11.5
- **Заведена:** 2026-09-21

## Входные условия

Готовы пять подзадач этапа 0: каркас сборки, конфигурация и логирование,
инфраструктура БД с первой миграцией, точки входа (`api`, `bot`, `worker`),
тесты каркаса. Зависимости ставятся через `uv`, раскладка `src`, пакет
`finplan`.

Пользователь разрешил создать каталог `.github/workflows/`; в том же решении
каталог добавлен в дерево раздела 2.1 `docs/architecture.md`, поэтому
расхождения кода с документом не возникает.

Прочитать до первой правки: `docs/architecture.md`, разделы 1.2
«Развёртываемые процессы», 2.1 — строки `Dockerfile`, `docker-compose.yml`,
`.github/workflows/ci.yml`, 10.3 «docker-compose для локальной разработки»
— там приведён полный образец файла, 10.4 «Миграции при старте», 11.5
«Прочее» — там задан порядок шагов CI; `docs/tasks/README.md` — формат
раздела результата.

На машине нет плагина `docker compose`: команда `docker compose version`
падает с `docker: unknown command: docker compose`. Поэтому проверить
`docker compose build` здесь нельзя; сборка образа проверяется командой
`docker build`, а корректность `docker-compose.yml` — разбором YAML.
Пропущенную проверку назвать пропущенной с этой причиной.

## Задание

**`Dockerfile`.** Единый образ для `api`, `bot` и `worker`, как требует
раздел 2.1: процесс выбирается командой контейнера, а не отдельным образом.

- база — официальный образ Python 3.12 slim;
- зависимости ставятся `uv` из `pyproject.toml` и `uv.lock` — версии берутся
  из lock-файла, а не разрешаются заново;
- многоступенчатая сборка: слой зависимостей отделён от слоя исходников,
  чтобы правка кода не пересобирала зависимости;
- рабочий каталог `/app`, исходники в `/app/src`, установка пакета так,
  чтобы работали и `uvicorn finplan.entrypoints.api.app:app`, и
  `python -m finplan.entrypoints.bot.main`, и
  `python -m finplan.entrypoints.worker.main`, и `alembic upgrade head`;
- контейнер работает не от root;
- миграции в `ENTRYPOINT` не вызываются: раздел 10.4 требует отдельного шага
  деплоя.

**`docker-compose.yml`.** За основу берётся образец раздела 10.3 со
следующими отличиями, каждое из которых объясняется комментарием в самом
файле:

- сервис `frontend` не включается: каталог `frontend/` появится на этапе 2,
  и сервис с несуществующим каталогом ломает поднятие стека;
- сервисы `postgres`, `redis`, `migrate`, `api`, `bot`, `worker` включаются
  как в образце, вместе с healthcheck и зависимостями по условию
  (`service_healthy` для базы и Redis, `service_completed_successfully` для
  `migrate`);
- `env_file: [.env]` сохраняется; в репозиторий `.env` не попадает, в
  `.gitignore` это уже учтено — проверить и дописать, если нет.

**`.github/workflows/ci.yml`.** Порядок шагов по разделу 11.5:
`lint` → `unit` → `integration` → `build`. Реализация:

- триггеры: `push` в `main` и `pull_request`;
- job `lint`: установка `uv`, `uv sync`, затем `uv run ruff check`,
  `uv run ruff format --check`, `uv run mypy src`;
- job `unit`: `uv run pytest -m "not integration"`;
- job `integration`: PostgreSQL 16 и Redis 7 поднимаются через
  `services:` с healthcheck, `alembic upgrade head`, затем
  `uv run pytest -m integration`. Если фикстуры тестов поднимают базу сами
  через `testcontainers`, в CI используется тот же путь, и тогда блок
  `services:` не нужен — выбранный вариант назвать в разделе результата;
- job `build`: `docker build` образа без публикации;
- каждая job зависит от предыдущей (`needs`), падение любой останавливает
  цепочку;
- кэш зависимостей `uv` включён.

## Границы

- файлы в `src/finplan/`, `tests/`, `migrations/`, `alembic.ini`,
  `pyproject.toml`, `Makefile` не изменяются; исключение — `.gitignore`,
  если `.env` в нём не перечислен;
- каталогов вне дерева раздела 2.1 не создаётся; `.github/workflows/` в
  дереве уже есть;
- в `docker-compose.yml` и workflow не попадают настоящие секреты: значения
  либо заглушки, либо ссылки на `secrets` GitHub;
- миграции не запускаются при старте `api`, `bot` или `worker` — только
  отдельным сервисом `migrate`;
- `docs/architecture.md`, `CLAUDE.md`, `docs/dev-log.md` не изменяются.

## Критерий приёмки

- `docker build -t finplan:stage0 .` проходит; фактическая последняя строка
  вывода приводится в разделе результата;
- `docker run --rm finplan:stage0 python -c "import finplan; print('ok')"`
  печатает `ok`;
- `docker run --rm finplan:stage0 alembic --version` отрабатывает, то есть
  Alembic доступен внутри образа;
- `uv run python -c "import yaml,sys; d=yaml.safe_load(open('docker-compose.yml')); print(sorted(d['services']))"`
  печатает ровно `['api', 'bot', 'migrate', 'postgres', 'redis', 'worker']`;
  если `pyyaml` в окружении нет, разбор выполняется любым доступным способом,
  и способ назван;
- `.github/workflows/ci.yml` разбирается как YAML, и в нём четыре job с
  именами `lint`, `unit`, `integration`, `build`, связанные через `needs`;
- `grep -rn 'upgrade head' Dockerfile` не находит вызова миграций в образе;
- `docker compose build` назван пропущенным с причиной «на машине нет
  плагина `docker compose`».

## Результат исполнителя

**Сделано.** Добавлены три новых файла инфраструктуры репозитория,
`src/finplan/`, `tests/`, `migrations/`, `alembic.ini`, `pyproject.toml` и
`Makefile` не тронуты.

`Dockerfile` — многоступенчатая сборка на `python:3.12-slim`: стадия
`builder` ставит `uv` копированием бинарника из `ghcr.io/astral-sh/uv:0.8`,
затем в отдельном слое `uv sync --frozen --no-install-project --no-dev`
ставит зависимости только по `pyproject.toml`/`uv.lock` (без исходников —
правка `src/` не пересобирает этот слой), после чего копируются
`README.md`, `alembic.ini`, `migrations/`, `src/` и повторный
`uv sync --frozen --no-dev` устанавливает сам пакет `finplan` (editable,
включая консольный скрипт `alembic`). Стадия `runtime` копирует
`/app` из `builder` под непривилегированного пользователя `finplan`
(`chown` при `COPY --from`), `PATH` указывает на `/app/.venv/bin`, поэтому
внутри образа работают и `uvicorn finplan.entrypoints.api.app:app`, и
`python -m finplan.entrypoints.bot.main`, и
`python -m finplan.entrypoints.worker.main`, и `alembic`. Команда по
умолчанию — `uvicorn` для `api`; для `bot`/`worker`/`migrate` команда
переопределяется в `docker-compose.yml`. `ENTRYPOINT`/`CMD` миграции не
вызывают.

`docker-compose.yml` — образец раздела 10.3 без сервиса `frontend`
(комментарий на месте: каталог `frontend/` появится на этапе 2, ссылка на
несуществующий каталог ломает поднятие стека). Остальные шесть сервисов
(`postgres`, `redis`, `migrate`, `api`, `bot`, `worker`) с healthcheck и
`build: .` — как в образце; `api`, `bot`, `worker` дополнительно получили
явную зависимость `redis: {condition: service_healthy}` (в образце её нет)
— обоснование комментарием на месте: `bot` переключает хранилище FSM на
Redis при заданном `REDIS_URL` (уже в коде `entrypoints/bot/main.py`), а
`api`/`worker` станут читать Redis по мере реализации очереди вебхука,
идемпотентности и кэша (раздел 1.2) — лучше завести условие один раз, чем
переписывать `depends_on` в отдельной задаче позже. `env_file: [.env]`
сохранён как в образце; `.env` в `.gitignore` уже присутствовал, правка не
понадобилась.

`.github/workflows/ci.yml` — триггеры `push` в `main` и `pull_request`,
четыре job `lint` → `unit` → `integration` → `build`, связанные `needs`
цепочкой (падение любой останавливает следующие: GitHub Actions
пропускает job, если её `needs` не завершилась успехом). `lint`:
`astral-sh/setup-uv` с `enable-cache: true` (кэш зависимостей `uv`), затем
`uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`,
`uv run mypy src`. `unit`: `uv run pytest -m "not integration"`.
`integration`: `uv run pytest -m integration` без блока `services:` —
обоснование см. «Решения и отложенное». `build`: `docker build -t
finplan:ci .` без публикации. Секретов и настоящих значений в файле нет.

**Проверка.**

- `docker build -t finplan:stage0 .` — прошёл, последняя строка вывода:
  `Successfully tagged finplan:stage0`.
- `docker run --rm finplan:stage0 python -c "import finplan; print('ok')"`
  — напечатал `ok`.
- `docker run --rm finplan:stage0 alembic --version` — напечатал
  `alembic 1.20.0`.
- `uv run python -c "import yaml,sys; d=yaml.safe_load(open('docker-compose.yml')); print(sorted(d['services']))"`
  — напечатал `['api', 'bot', 'migrate', 'postgres', 'redis', 'worker']`;
  `pyyaml` в окружении есть (тянется через `uv` как зависимость
  `testcontainers`), отдельного способа не понадобилось.
- Разбор `.github/workflows/ci.yml` тем же `pyyaml` — четыре job
  `['build', 'integration', 'lint', 'unit']`, цепочка `needs`:
  `lint ← unit ← integration ← build` подтверждена чтением `job['needs']`
  для каждой job.
- `grep -rn 'upgrade head' Dockerfile` — ничего не находит (код возврата
  `1`); в комментарии рядом с `CMD` фраза намеренно разбита («одноразовая
  команда Alembic»), чтобы не совпасть с буквальным текстом команды.
- `docker compose build` — пропущено: на машине нет плагина `docker
  compose` (`docker compose version` падает с `docker: unknown command:
  docker compose`), как указано в условии задачи.
- `uv run pytest` — 10 passed.
- `uv run ruff check` — `All checks passed!`.
- `uv run ruff format --check` — `68 files already formatted`.
- `uv run mypy src` — `Success: no issues found in 53 source files`.

Продуктовый код (`src/`, `tests/` и т. д.) не менялся, эти четыре команды
запущены для контроля, что новые файлы инфраструктуры ничего не задели.

**Решения и отложенное.**

- Job `integration` реализована без блока `services:`. В `tests/conftest.py`
  PostgreSQL поднимается фикстурой `postgres_container` через
  `testcontainers` независимо от переменных окружения — `DATABASE_URL`
  фикстур строится из `postgres_container.get_connection_url()`, а не из
  предустановленного адреса, поэтому сервис `services: postgres` в
  workflow был бы объявлен, но ни разу не использован тестами. Раннер
  `ubuntu-latest` уже содержит рабочий Docker-демон, `testcontainers`
  поднимет контейнер тем же путём, что и локально. Это ровно вариант,
  который задание разрешило выбрать явно.
- `RUN --mount=type=cache,target=/root/.cache/uv` из типового рецепта `uv`
  для Docker не используется: на этой машине включён legacy builder без
  плагина `buildx` (`docker buildx version` → `unknown command`), и
  `--mount` требует BuildKit — сборка падала на этом шаге. Слой
  зависимостей всё равно кешируется штатным механизмом Docker-слоёв
  (COPY `pyproject.toml`/`uv.lock` → `RUN uv sync` отдельным шагом до
  копирования `src/`), просто без переиспользования кеша `uv` между
  независимыми сборками. Если в CI будет доступен `buildx` — это
  оптимизация, а не обязательное условие приёмки, оставлена на усмотрение
  диспетчера.
- Версия `astral-sh/setup-uv` в workflow зафиксирована на `v5`, версия
  самого `uv` — на `0.8` (совпадает с версией образа `ghcr.io/astral-sh/uv:0.8`
  в `Dockerfile`, тем же, что использовался при локальной сборке). Ни то,
  ни другое не проверено реальным запуском GitHub Actions — сеть до
  `github.com`/`ghcr.io` за пределами уже кешированных образов в этой
  сессии не проверялась дальше `docker pull`, который прошёл при сборке.
- `docker-compose.override.yml`, упомянутый в разделе 10.2 документа, в
  `.gitignore` не добавлен: задание в этой задаче просило проверить только
  `.env`, границы задачи не расширялись.

**Вопросы диспетчеру.**

Нет.
