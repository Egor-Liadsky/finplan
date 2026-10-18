# CI/CD finplan

Непрерывная интеграция целиком лежит в одном workflow — [`ci.yml`](ci.yml).
Он проверяет каждый push в `main` и каждый pull request и в конце собирает
Docker-образ приложения. Непрерывной доставки в репозитории нет: образ не
публикуется в реестр, ни на одном окружении ничего не разворачивается,
деплой пока ручной. Этот файл описывает, что проверяется, в каком порядке и
как повторить те же проверки локально.

Требование к порядку шагов задаёт `docs/architecture.md`, раздел 11.5
«Прочее» (строка 3128): `lint` → `unit` → `integration` → `build`.
Расхождение фактического workflow с этим разделом указано ниже, в разделе
«Интеграционные тесты».

## Состав каталога

| Файл | Назначение |
|---|---|
| `ci.yml` | Единственный workflow: общие переменные и четыре job |
| `README.md` | Этот документ |

## Триггеры и общие переменные

- `push` в ветку `main` и `pull_request` без фильтра ветвей (`ci.yml:6-9`) —
  любой PR проходит тот же workflow, что и `main`.
- `env.UV_VERSION: "0.8"` (`ci.yml:11-14`) — единственная переменная уровня
  workflow. Она передаётся в `astral-sh/setup-uv` как `version`
  (`ci.yml:22-25`, повторяется в `unit` и `integration` — `ci.yml:43-46`,
  `ci.yml:67-70`). Та же версия `uv` зашита тегом образа
  `ghcr.io/astral-sh/uv:0.8` в `Dockerfile:15`, поэтому локальная сборка
  образа и CI ставят зависимости одним и тем же `uv`.
- Секретов в workflow нет: значений, которые нужно скрывать, он не
  использует. Тестам хватает синтаксически корректных заглушек, которые
  `tests/conftest.py:56-63` подставляет через `os.environ.setdefault`, —
  настоящие `DATABASE_URL`, `TELEGRAM_BOT_TOKEN` и `JWT_SECRETS` в CI не
  нужны.

## Цепочка job'ов

Каждая следующая job объявляет предыдущую в `needs`
(`ci.yml:38`, `ci.yml:62`, `ci.yml:79`), поэтому падение любого шага
останавливает цепочку: зависимые job'ы не запускаются вовсе. Это и есть
техническая часть правила «ветка не сливается при падении любого шага»
(раздел 11.5, строка 3130) — вторая половина, защита ветки от слияния,
настраивается в самом GitHub, а не в файле workflow.

| Job | `needs` | Что делает | Что означает красный статус |
|---|---|---|---|
| `lint` | — | `ruff check`, `ruff format --check`, `mypy src` | Нарушен стиль, форматирование или типы |
| `unit` | `lint` | `pytest -m "not integration"` | Сломан модульный тест или тест без внешних зависимостей |
| `integration` | `unit` | `pytest -m integration` | Сломан тест против реальной PostgreSQL 16 |
| `build` | `integration` | `docker build -t finplan:ci .` | `Dockerfile` не собирается |

Общий пролог у всех job'ов одинаковый: `actions/checkout@v4`
(`ci.yml:20`, `41`, `65`, `82`), затем в `lint`, `unit` и `integration` —
`astral-sh/setup-uv@v5` с `enable-cache: true`, `uv python install 3.12` и
`uv sync --locked`. Кэш `uv` включён во всех трёх job'ах, где он нужен;
`build` ставит зависимости внутри образа и `setup-uv` не вызывает.

`uv sync --locked` (а не `uv sync`) — намеренно: если `pyproject.toml` и
`uv.lock` разошлись, job падает сразу, а не подтягивает свежие версии
зависимостей в обход lock-файла. После правки зависимостей нужен локальный
`uv lock`, иначе CI покраснеет.

## Job `lint`

`ci.yml:17-35`; версия Python задана явно (`uv python install 3.12`,
`ci.yml:27`) и совпадает с `requires-python = ">=3.12,<3.13"` из
`pyproject.toml:6`; матрицы версий нет.

- `uv run ruff check` (`ci.yml:31`) — правила `E`, `F`, `I`, `UP`, `B`,
  `N`, `RUF` при `line-length = 100`, каталог `docs` исключён
  (`pyproject.toml:41-49`).
- `uv run ruff format --check` (`ci.yml:33`) — проверка форматирования без
  правки файлов.
- `uv run mypy src` (`ci.yml:35`) — `strict = false` для всего пакета, но
  `finplan.domain.*` и `finplan.application.*` проверяются в strict-режиме
  (`pyproject.toml:51-60`), то есть границы слоёв подпираются ещё и типами.

## Job `unit`

`ci.yml:37-52`, единственный шаг проверки — `uv run pytest -m "not
integration"` (`ci.yml:52`). Маркеры объявлены в `pyproject.toml:62-69`:
`unit`, `integration`, `e2e`; `testpaths = ["tests"]`.

Из селектора следуют два неочевидных факта:

- в job попадают не только `tests/unit`, но и всё, что не помечено
  `integration`, — например `tests/integration/bot/test_start.py`, которому
  база не нужна: он подменяет транспорт `BaseSession` и работает без
  Docker;
- будущие `tests/e2e` (сейчас каталог пуст) тоже пойдут в эту job, пока их
  не пометят отдельно, — отдельной job под маркер `e2e` в workflow нет.

## Job `integration`

`ci.yml:61-76`: `uv run pytest -m integration` (`ci.yml:76`). Блока
`services:` в workflow нет, и это осознанно — обоснование записано
комментарием в самом файле (`ci.yml:54-60`): PostgreSQL 16 поднимает не
GitHub, а фикстура `postgres_container` в `tests/conftest.py:161-174` через
`testcontainers`, тем же путём, что и при локальном запуске. Раннер
`ubuntu-latest` уже содержит рабочий Docker-демон, поэтому контейнер
стартует без дополнительной настройки.

Что именно поднимается и проверяется:

- `PostgresContainer("postgres:16-alpine")`, один раз на сессию pytest;
  роли `finplan_app` и `finplan_worker` создаются сразу после старта
  контейнера (`tests/conftest.py:113-146`), иначе миграция с RLS падает;
- миграции применяются не отдельным шагом CI, а фикстурами:
  `migrated_database` (`tests/conftest.py:210`) для большинства
  интеграционных тестов и `fresh_database_url` (`tests/conftest.py:248`)
  для тестов, которым нужна пустая схема;
- цикл `upgrade head` → `downgrade base` → `upgrade head` и сверка схемы с
  метаданными SQLAlchemy через `alembic check` живут в тестах
  (`tests/integration/test_migrations.py:44-98`), поэтому отдельного шага
  `alembic upgrade head` в workflow нет и он не нужен;
- Redis интеграционным тестам не требуется: ни одна фикстура его не
  поднимает.

Отсюда известное расхождение с документом: раздел 11.5
(`docs/architecture.md:3129`) говорит, что интеграционные тесты используют
`services: postgres` и Redis, тогда как реализация — `testcontainers` и
только PostgreSQL. Причина выбора записана в `ci.yml:54-60` и в отчёте
`docs/tasks/done/2026-09-21-stage0-docker-ci.md`. Пока блок `services:` не
появится в workflow, эту фразу раздела 11.5 нельзя читать как описание
фактического CI.

Если Docker на машине недоступен, тесты с маркером `integration` не падают,
а пропускаются на этапе сбора с сообщением «Docker недоступен»
(`tests/conftest.py:94-110`). В CI это не срабатывает: демон есть.

## Job `build`

`ci.yml:78-84`: единственный шаг `docker build -t finplan:ci .`
(`ci.yml:84`) — сборка образа без публикации и без `setup-uv`, потому что
все зависимости ставятся внутри `Dockerfile` (многоступенчатая сборка:
`builder` — `Dockerfile:10-37`, `runtime` — `Dockerfile:39-58`). Сборке
нужны `pyproject.toml`, `uv.lock` (`Dockerfile:27`), `README.md`,
`alembic.ini`, `migrations/` и `src/` (`Dockerfile:32-35`): отсутствие
любого из них ломает job, даже если тесты зелёные. Кэша слоёв Docker в этой
job нет — каждый прогон собирает образ с нуля.

## Чего CI не делает

- Не запускает `python3 docs/build-brief.py --check`, хотя эта проверка
  входит в `make lint` (`Makefile:21-25`): рассинхронизация
  `docs/architecture-brief.md` с `docs/architecture.md` локально ловится, а
  в CI — нет.
- Не считает покрытие и не сравнивает его с порогом: `coverage` есть в
  dev-зависимостях (`pyproject.toml:23-32`), но в workflow не вызывается.
- Не публикует образ и ничего не деплоит — `build` заканчивается на
  локальном теге `finplan:ci`.
- Не запускает проверки отдельно для `docs/` и Markdown: `ruff` этот
  каталог исключает (`pyproject.toml:43`).

## Как повторить проверки локально

```bash
uv sync --locked
uv run ruff check
uv run ruff format --check
uv run mypy src
uv run pytest -m "not integration"   # job unit
uv run pytest -m integration         # job integration, нужен Docker
docker build -t finplan:ci .         # job build
```

`make lint` — это те же три команды плюс сверка выжимки, `make test` — это
`uv run pytest` по всем уровням сразу (`Makefile:15-16`, `Makefile:21-25`),
поэтому локальные ярлыки строже CI: зелёный CI не гарантирует зелёный
`make lint`.

## Правила правки workflow

- Порядок job'ов и связки `needs` менять только вместе с разделом 11.5
  `docs/architecture.md`: это требование документа, а не деталь реализации.
- Новую job вставлять в цепочку через `needs`, а не параллельно ей, — иначе
  падение шага перестанет останавливать сборку образа.
- Каждой job'е, где запускается Python, нужны `setup-uv` с
  `enable-cache: true`, `uv python install 3.12` и `uv sync --locked`.
- Настоящие токены и пароли в workflow не добавлять: тестам достаточно
  заглушек из `tests/conftest.py:56-63`, а боевые значения хранятся в
  секрет-хранилище платформы развёртывания (раздел 12.6,
  `docs/architecture.md:3264-3265`).
