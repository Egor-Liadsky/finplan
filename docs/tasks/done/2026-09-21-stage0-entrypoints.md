# Точки входа: health-check API, бот на /start, пустой worker

- **Исполнитель:** developer
- **Слой:** entrypoints
- **Раздел архитектуры:** docs/architecture.md, разделы 1.2, 2.2, 7.6, 10.4, 10.5, 12.1
- **Заведена:** 2026-09-21

## Входные условия

Готовы подзадачи «Каркас сборки», «Конфигурация и логирование»,
«Инфраструктура БД»: есть `Settings` и `get_settings()`,
`configure_logging()` со структурированным контекстом `request_id` и
`user_id`, async engine и sessionmaker в
`infrastructure/db/engine.py`, функция сравнения ревизии `alembic_version`
с `head`, первая миграция создаёт `users` и `currencies`.

Прочитать до первой правки: `docs/architecture.md`, разделы 1.2
«Развёртываемые процессы», 2.2 «Правила слоёв», 7.6 «Общие заголовки и
политики», 10.4 «Миграции при старте», 10.5 «Режим бота», 12.1
«Логирование», 13 «Этап 0»; `src/finplan/config.py` и `logging.py`;
`docs/tasks/README.md` — формат раздела результата.

## Задание

Три процесса из раздела 1.2 должны запускаться и отвечать. Бизнес-логики в
них нет: этап 0 даёт каркас, а не поведение.

**`entrypoints/api/app.py`.** Сборка FastAPI: фабрика `create_app()` и
модульный объект `app`, чтобы работала команда
`uvicorn finplan.entrypoints.api.app:app` из раздела 10.3.

- `lifespan` настраивает логирование, создаёт engine и кладёт его в состояние
  приложения, а на выходе закрывает; **миграции не применяет** — по разделу
  10.4 при старте выполняется только сравнение ревизии в `alembic_version`
  с `head`, и при расхождении процесс отказывается стартовать с сообщением,
  называющим обе ревизии;
- CORS настраивается из `CORS_ORIGINS`;
- middleware проставляет `request_id`: берёт его из заголовка `X-Request-ID`,
  если он пришёл, иначе генерирует, кладёт в контекст `structlog` и
  возвращает тем же заголовком в ответе;
- `/docs` доступен только при `APP_DEBUG=true`;
- роутер `entrypoints/api/routers/health.py` с эндпоинтом `GET /health`:
  отвечает `200` и телом, где есть состояние приложения, версия приложения и
  результат проверки соединения с БД (`SELECT 1`). Если база недоступна,
  ответ `503` с тем же телом и признаком неудачи. Эндпоинт не требует
  аутентификации и не входит в префикс `/api/v1`.

**`entrypoints/bot/main.py`.** Запуск aiogram 3: создание `Bot` и
`Dispatcher`, режим берётся из `TELEGRAM_MODE`; в этапе 0 поддерживается
`polling`, а при `webhook` процесс завершается понятным сообщением, что
режим появится вместе с приёмом вебхука в `api` (раздел 1.3). FSM-хранилище:
`MemoryStorage`, если `REDIS_URL` не задан, иначе `RedisStorage` — по
таблице раздела 10.1. Модуль запускается как `python -m finplan.entrypoints.bot.main`.

Роутер `entrypoints/bot/routers/start.py` с хендлером команды `/start`:
отвечает коротким текстом-заглушкой о том, что бот запущен и учёт появится
дальше. Никаких обращений к базе, никакого создания пользователя — это
этап 1.

**`entrypoints/worker/main.py`.** Запуск APScheduler без единой
зарегистрированной job: планировщик стартует, если `SCHEDULER_ENABLED`
истинно, логирует пустой список задач и работает до сигнала завершения. При
`SCHEDULER_ENABLED=false` процесс сообщает об этом и завершается кодом 0.
Модуль запускается как `python -m finplan.entrypoints.worker.main`. Он нужен
в этапе 0 потому, что `docker-compose.yml` из раздела 10.3 поднимает сервис
`worker`, и сервис обязан стартовать.

Все три процесса в начале работы вызывают `configure_logging`, и в их логах
видно, какой процесс запустился и в каком режиме. Секреты в логи не
попадают.

## Границы

- бизнес-логики в `entrypoints/**` нет: ни расчётов, ни доменных правил, ни
  создания пользователя в базе;
- `domain/**` и `application/**` не изменяются и остаются пустыми пакетами:
  use case в этапе 0 не появляется;
- `infrastructure/**` не переписывается; если для проверки ревизии или
  соединения не хватает функции, она добавляется минимальной правкой, и
  правка называется в разделе результата;
- `config.py` и `logging.py` не переписываются;
- `container.py` в этой подзадаче не создаётся: композиция зависимостей
  появится, когда появятся use case;
- эндпоинтов, кроме `GET /health`, не добавляется; роутеры разделов 7.1 —
  этапы 1 и дальше;
- `Dockerfile`, `docker-compose.yml`, `.github/` не создаются;
- `docs/architecture.md`, `CLAUDE.md`, `docs/dev-log.md` не изменяются.

## Критерий приёмки

- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src`
  проходят;
- при поднятой PostgreSQL с применёнными миграциями запрос к `GET /health`
  через `httpx.ASGITransport` возвращает `200`, и тело содержит признак
  успешной проверки БД. Проверяется коротким скриптом `uv run python -c ...`
  или временным файлом, который после проверки удаляется; фактический ответ
  приводится в разделе результата;
- при базе, где миграции не применены (пустая схема), создание приложения
  или его запуск завершается ошибкой, называющей обе ревизии. Фактическое
  сообщение приводится в разделе результата;
- ответ на `GET /health` содержит заголовок `X-Request-ID`, и при передаче
  своего значения в запросе возвращается именно оно;
- `uv run python -c "from finplan.entrypoints.bot.main import dp"` (или иной
  импорт объекта `Dispatcher`) проходит без обращения к сети; хендлер
  `/start` зарегистрирован — проверяется тем, что список роутеров диспетчера
  непуст;
- `SCHEDULER_ENABLED=false uv run python -m finplan.entrypoints.worker.main`
  завершается кодом 0 и печатает строку лога о выключенном планировщике.

## Результат исполнителя

**Сделано.** Написан каркас трёх точек входа этапа 0 — `api`, `bot`,
`worker`. Бизнес-логики нет ни в одном из процессов; `domain/**` и
`application/**` не тронуты, `container.py` не создан.

`src/finplan/entrypoints/api/app.py`: фабрика `create_app()` и модульный
объект `app`, собранный ей же (`uvicorn finplan.entrypoints.api.app:app`
работает как есть). `lifespan` вызывает `configure_logging(settings)`,
создаёт async engine через `infrastructure.db.engine.create_engine` и
кладёт его в `app.state.engine`; **миграции не применяет** — только
`check_revision(connection)` из уже готового `infrastructure/db/revision.py`
(раздел 10.4). При расхождении ревизий исключение `RevisionMismatchError`
(с обеими ревизиями в сообщении) поднимается до выхода из `lifespan`,
приложение не стартует; при выходе engine закрывается через
`engine.dispose()` в `finally`. CORS настроен из `settings.cors_origins`
(`allow_credentials=True`, раздел 7.6). Мидлварь `request_id_middleware`
берёт `X-Request-ID` из входящего заголовка или генерирует новый (`uuid4`),
кладёт в контекст `structlog` через `bind_context`/`clear_context` и
возвращает тем же заголовком. `/docs`, `/redoc`, `/openapi.json` включены
только при `APP_DEBUG=true` (иначе `docs_url=None` и т. д., FastAPI отдаёт
404).

`src/finplan/entrypoints/api/routers/health.py`: роутер без префикса
`/api/v1`, эндпоинт `GET /health` без аутентификации. Делает `SELECT 1`
через `request.app.state.engine`; тело ответа — `status`, `version`
(`importlib.metadata.version("finplan")`) и `database.ok`. `200` при
успехе, `503` с тем же телом и `database.ok=False` при недоступной БД
(перехватывается `sqlalchemy.exc.SQLAlchemyError`, не голый `Exception`).

`src/finplan/entrypoints/bot/main.py`: модульные объекты `bot` (`Bot(token=…)`)
и `dp` (`Dispatcher(storage=…)`) с зарегистрированным `start_router` —
создаются без обращения к сети (валидация токена в aiogram — локальная,
regex, не HTTP-вызов; `RedisStorage.from_url` подключается лениво).
Хранилище — `MemoryStorage()`, если `settings.redis_url` не задан, иначе
`RedisStorage.from_url(settings.redis_url)` (раздел 10.1). `main()`
вызывает `configure_logging`, логирует старт, при `TELEGRAM_MODE=webhook`
пишет `logger.error` с точным пояснением («режим появится вместе с приёмом
вебхука в api, раздел 1.3») и завершает процесс `sys.exit(1)`; при
`polling` запускает `dp.start_polling(bot)` и закрывает `bot.session` в
`finally`. Модуль запускается как `python -m finplan.entrypoints.bot.main`
благодаря блоку `if __name__ == "__main__":`.

`src/finplan/entrypoints/bot/routers/start.py`: `Router(name="start")` с
хендлером `CommandStart()` — короткий текст-заглушка о том, что бот
запущен, без обращений к БД и созданию пользователя.

`src/finplan/entrypoints/worker/main.py`: `main()` вызывает
`configure_logging`, логирует старт. При `SCHEDULER_ENABLED=false`
логирует `worker.scheduler_disabled` и возвращается — процесс завершается
кодом 0. Иначе создаёт `AsyncIOScheduler()` без единой job, логирует
`worker.scheduler_starting` с пустым списком `jobs`, стартует планировщик и
ждёт `SIGINT`/`SIGTERM` через `asyncio.Event` и
`loop.add_signal_handler`, затем корректно останавливает планировщик.
Запускается как `python -m finplan.entrypoints.worker.main`.

Правка вне списка задания: не потребовалась — `infrastructure/**`,
`config.py`, `logging.py` не менялись, для проверки ревизии и соединения
хватило уже готовых `check_revision` и `create_engine`.

**Проверка.**

- `uv run ruff check` — `All checks passed!`.
- `uv run ruff format --check` — `63 files already formatted`.
- `uv run mypy src` — `Success: no issues found in 53 source files`.
- `uv run pytest` — `collected 0 items`, `no tests ran in 0.09s`: в
  `tests/**` пока только `.gitkeep`, тестов для этой подзадачи не заводилось
  (не входит в задание, слой `entrypoints` тестируется отдельной
  подзадачей `tester`).
- `GET /health` через `httpx.ASGITransport` с реальным `lifespan`
  (`async with app.router.lifespan_context(app):`, БД `finplan` на `head`):
  `STATUS 200`, `BODY {'status': 'ok', 'version': '0.1.0', 'database':
  {'ok': True}}`; `X-Request-ID` без заголовка в запросе —
  `8d784859-3dd3-4a43-81b6-7d7c14273592` (сгенерирован), с заголовком
  `X-Request-ID: client-supplied-id` в запросе — тот же `client-supplied-id`
  в ответе.
- Сценарий незавершённых миграций: временная база `empty_check` в том же
  контейнере `finplan-pg` (`CREATE DATABASE empty_check`, затем удалена
  `DROP DATABASE empty_check`, основная база `finplan` не трогалась).
  `DATABASE_URL` указывал на `empty_check` (пустая схема, `alembic_version`
  нет). `async with app.router.lifespan_context(app):` падает с:
  `finplan.infrastructure.db.revision.RevisionMismatchError: database
  revision is None, code head is 'fc2037cdf9d2': run 'alembic upgrade
  head' before starting the app` — обе ревизии названы. Дополнительно
  проверено реальным процессом `uv run uvicorn
  finplan.entrypoints.api.app:app` против той же пустой базы: лог
  завершается `ERROR: Application startup failed. Exiting.` с тем же
  traceback и тем же сообщением `RevisionMismatchError`.
- `/docs`: при `APP_DEBUG=false` — `404`; при `APP_DEBUG=true` — `200`
  (оба сценария прогнаны через `httpx.ASGITransport` с реальным
  `lifespan`).
- `uv run python -c "from finplan.entrypoints.bot.main import dp"` (с
  корректно оформленным фиктивным токеном, без сети) — импорт проходит,
  `len(dp.sub_routers) == 1`, `[r.name for r in dp.sub_routers] ==
  ['start']`.
- `TELEGRAM_MODE=webhook uv run python -m finplan.entrypoints.bot.main` —
  завершается кодом 1, лог `bot.webhook_not_supported` с пояснением про
  раздел 1.3 и `TELEGRAM_MODE=polling`.
- `SCHEDULER_ENABLED=false uv run python -m finplan.entrypoints.worker.main`
  — код возврата `0`, лог содержит `"event": "worker.scheduler_disabled",
  "detail": "SCHEDULER_ENABLED=false"`.
- `SCHEDULER_ENABLED=true` — процесс стартует, лог
  `"event": "worker.scheduler_starting", "jobs": []`, затем `Scheduler
  started`; после `SIGTERM` — `process.stopped` и `Scheduler has been shut
  down`, процесс завершается штатно.
- Контейнер `finplan-pg` не останавливался и не удалялся; после всех
  проверок в нём остаётся только рабочая база `finplan` на ревизии
  `fc2037cdf9d2`, временная `empty_check` удалена.

**Решения и отложенное.**

- Раздел 12.1 требует ULID для `request_id`, но библиотеки ULID нет в
  зависимостях `pyproject.toml` (только те, что уже перечислены в проекте).
  Добавление новой зависимости — решение уровня диспетчера, не подзадачи
  `entrypoints`; middleware генерирует `uuid4` вместо ULID. Формат
  генерируемого id не проверяется критерием приёмки, но это расхождение с
  документом, а не самостоятельная замена архитектурного решения.
  Называю в вопросах диспетчеру ниже.
- Заголовок в задании назван `X-Request-ID` (капс `ID`), а в разделе 7.6
  документа — `X-Request-Id`. HTTP-заголовки регистронезависимы, поэтому
  поведение не отличается; в коде использовано написание `X-Request-ID` по
  буквальному тексту задания.
- `TELEGRAM_BOT_TOKEN=changeme` из `.env.example` не проходит локальную
  (не сетевую) валидацию формата токена в aiogram
  (`aiogram.utils.token.validate_token`) — конструктор `Bot()` поднимает
  `TokenValidationError` уже при импорте `bot.main`. Для проверки критерия
  приёмки использовался токен `123456789:AAFakeTokenForLocalTestingOnly…` —
  синтаксически похожий на настоящий, без реального обращения к
  `api.telegram.org`. Файл `.env.example` не в границах этой подзадачи, не
  правился; называю находку в вопросах диспетчеру.
- Тело ответа `/health` и код возврата `RevisionMismatchError` — простые
  словари/сообщения, без отдельной Pydantic-схемы в
  `entrypoints/api/schemas/`: в задании не сказано заводить схему для этого
  единственного эндпоинта каркаса, а сам каталог `schemas/` в дереве
  раздела 2.1 предназначен для схем HTTP из раздела 7 (этапы 1+).
- `worker/main.py` использует `loop.add_signal_handler` — не работает на
  Windows, но раздел 1.2 и `docker-compose.yml` подразумевают
  Linux-контейнеры; для локальной разработки на macOS (эта сессия)
  проверено и работает.
- `tests/**` этой подзадачей не писались — раздел «Задание» и «Границы» их
  не требуют, слой `entrypoints` для тестирования — предмет отдельной
  подзадачи `tester`.

**Вопросы диспетчеру.**

- Раздел 12.1 `docs/architecture.md` требует `request_id` в формате ULID,
  но в `pyproject.toml` нет соответствующей библиотеки (например,
  `python-ulid`). Сейчас `request_id` — `uuid4`. Нужно решение: добавить
  зависимость и переключить на ULID, оставить `uuid4` и поправить документ,
  или это осознанно отложено до появления реальной необходимости в
  сортируемых по времени id?
- `.env.example`: `TELEGRAM_BOT_TOKEN=changeme` не проходит локальную
  валидацию формата токена в aiogram 3 (`Bot()` поднимает
  `TokenValidationError` уже при создании объекта, без сети). Значение,
  видимо, стоит заменить на синтаксически корректную заглушку вида
  `123456789:AAFakePlaceholderToken...`, чтобы `python -m
  finplan.entrypoints.bot.main` и любой код, импортирующий `bot.main`, не
  падали на дефолтном `.env`. Правка `.env.example` вне границ этой
  подзадачи — передаю на усмотрение диспетчера.

