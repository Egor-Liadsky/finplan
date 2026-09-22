# finplan

Система личного финансового учёта: операции вводятся короткими сообщениями
Telegram-боту, а разбор, фильтрация и аналитика происходят в веб-интерфейсе
на большом экране. Один пользователь — один изолированный учёт: счета,
категории, журнал операций, капиталы, бюджеты, цели накопления и вклады.
Приём платежей, интеграция с банками и бухгалтерия юридических лиц вне
рамок проекта.

## Статус

Проект находится на этапе 0 «Каркас» из раздела 13
[`docs/architecture.md`](docs/architecture.md). Готов репозиторий, в
котором можно писать код и разворачивать стек, — продуктовой
функциональности пока нет.

Что работает:

- конфигурация (`pydantic-settings`) и структурное логирование
  (`structlog`);
- подключение к PostgreSQL и Alembic; первая миграция создаёт таблицы
  `currencies` и `users` и наполняет справочник валют;
- процесс `api` с единственным эндпоинтом `GET /health`, который проверяет
  доступность базы и отказывается стартовать при расхождении ревизии БД с
  `head`;
- процесс `bot`, отвечающий на `/start` заглушкой;
- процесс `worker` с пустым списком заданий планировщика;
- сборка образа, локальный стек `docker-compose` и CI в GitHub Actions.

Чего ещё нет: доменных сущностей и расчётов (`domain/entities`,
`domain/finance` — пустые пакеты), use cases (`application/use_cases/*` —
только `__init__.py`), репозиториев, HTTP-API для SPA, диалогов бота и
каталога `frontend/`. Всё это описано в архитектуре как целевое состояние
и распределено по этапам 1–7 раздела 13.

## Компоненты

| Компонент | Назначение |
|---|---|
| `api` | HTTP-API для SPA и приём вебхука Telegram; uvicorn, FastAPI |
| `bot` | Обработка апдейтов Telegram и диалоги FSM; aiogram 3 |
| `worker` | Планировщик и фоновые задачи; APScheduler |
| `postgres` | Единственный источник истины по данным |
| `redis` | FSM-состояния бота, кэш, идемпотентность, rate limit |
| SPA | Просмотр и аналитика в браузере; каталога `frontend/` пока нет |

Три Python-процесса собираются из одного образа и различаются только
командой запуска — доменный код во всех точках входа заведомо одной
версии. Подробности о процессах — раздел 1
[`docs/architecture.md`](docs/architecture.md).

## Архитектура

Слои и направление зависимостей: `entrypoints` → `application` →
`domain`, а `infrastructure` реализует порты, объявленные в
`application`. Домен — чистый Python без IO: он не импортирует ни
SQLAlchemy, ни aiogram, ни FastAPI. Прикладной слой знает только о домене
и собственных портах; конкретные реализации подставляются при сборке
зависимостей. Точки входа бизнес-логики не содержат: разбирают вход,
вызывают use case, форматируют ответ.

Направление зависимостей не оставлено на дисциплину: тест
`tests/unit/test_layering.py` разбирает импорты всех файлов
`src/finplan/**` и падает на запрещённом. Из принятых соглашений действуют
также два счётных: денежные величины хранятся в `Decimal` внутри value
object `Money` и никогда во `float`, а периоды задаются полуинтервалом
`[from, to)`.

Полное описание структуры каталогов, доменной модели, схемы БД, API и
сценариев бота — в [`docs/architecture.md`](docs/architecture.md); README
их не пересказывает.

## Технологии

- Бэкенд: Python 3.12, FastAPI, uvicorn, aiogram 3, SQLAlchemy 2.x с
  asyncpg, Alembic, pydantic 2, pydantic-settings, structlog, APScheduler,
  redis, httpx, python-ulid.
- Хранилища: PostgreSQL 16, Redis 7.
- Фронтенд (планируется): React 18, TypeScript, Vite, TanStack Query,
  TanStack Table, Recharts.
- Разработка: `uv` для зависимостей и запуска команд, `ruff`, `mypy`
  (strict для `domain` и `application`), `pytest` с `pytest-asyncio`,
  `hypothesis`, `testcontainers`, `coverage`, `alembic`.

## Быстрый старт

Нужны Docker с плагином `compose` и [`uv`](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
uv sync
make up
curl http://localhost:8000/health
```

`make up` поднимает `postgres`, `redis`, одноразовый сервис `migrate` и
затем `api`, `bot`, `worker`. Миграции применяет сервис `migrate` до
старта остальных процессов, поэтому отдельно вызывать `make migrate`
после `make up` не нужно: эта цель запускает `alembic upgrade head`
локально и рассчитана на работу вне Docker.

Значения в `.env.example` — заглушки. Хосты `DATABASE_URL`,
`WORKER_DATABASE_URL` и `REDIS_URL` заданы именами сервисов compose
(`postgres`, `redis`); для запуска процессов вне Docker замените их на
`localhost`. `TELEGRAM_BOT_TOKEN` синтаксически валиден, но Telegram его
не примет — настоящий токен получают у `@BotFather`, иначе процесс `bot`
падает с `TelegramUnauthorizedError`.

Успешный ответ `GET /health` — `200` с телом вида
`{"status":"ok","version":"0.1.0","database":{"ok":true}}`.

## Разработка

```bash
make test
make lint
make revision m="add transactions table"
make migrate
```

`make test` — это `uv run pytest`; `make lint` — `ruff check`,
`ruff format --check` и `mypy src`. Цели `make seed` и `make recalc`
объявлены, но пока печатают `not implemented yet: stage 1`.

Тесты разложены по уровням пирамиды из раздела 11 архитектуры:
`tests/unit` — чистый Python без внешних зависимостей; `tests/integration`
— проверки против реальной PostgreSQL 16, которую поднимает
`testcontainers` (сейчас это миграции, `GET /health` и хендлер `/start`);
`tests/e2e` — сквозные сценарии через оба диспетчера, пока пустой каталог.
Те же имена доступны как маркеры pytest: `unit`, `integration`, `e2e`.
SQLite в тестах не используется. Без запущенного Docker интеграционные
тесты пропускаются, а не падают.

## Документация проекта

- [`docs/architecture.md`](docs/architecture.md) — целевая архитектура,
  четырнадцать разделов: процессы, структура репозитория, доменная модель,
  схема БД, финансовые расчёты, сценарии бота, API, аутентификация,
  фоновые задачи, конфигурация, тестирование, нефункциональные требования,
  этапы внедрения, принятые решения и открытые вопросы.
- [`docs/dev-log.md`](docs/dev-log.md) — журнал разработки: что сделано,
  почему выбрано именно так, какой вариант отвергнут. Новые записи сверху.
- [`docs/tasks/README.md`](docs/tasks/README.md) — протокол передачи задач
  субагентам-исполнителям через файлы задач.
- [`CLAUDE.md`](CLAUDE.md) — роль ИИ-ассистента в репозитории: границы
  слоёв, ход работы, правила делегирования.

## Лицензия

MIT, см. файл [`LICENSE`](LICENSE).
