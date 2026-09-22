# Тесты каркаса: conftest, проверка слоёв, цикл миграций, health-check

- **Исполнитель:** tester
- **Слой:** tests
- **Раздел архитектуры:** docs/architecture.md, разделы 2.2, 11.1, 11.5
- **Заведена:** 2026-09-21

## Входные условия

Готовы четыре подзадачи этапа 0: каркас сборки, конфигурация и логирование,
инфраструктура БД с первой миграцией (`users`, `currencies`), точки входа
(`GET /health` в `api`, `/start` в боте, пустой `worker`). В
`pyproject.toml` уже объявлены `pytest`, `pytest-asyncio`, `hypothesis`,
`testcontainers[postgres]`, `coverage`; `asyncio_mode = "auto"`.

Прочитать до первой правки: `docs/architecture.md`, разделы 2.2 «Правила
слоёв», 11.1 «Пирамида», 11.5 «Прочее»; файлы задач
`docs/tasks/2026-09-21-stage0-db-alembic.md` и
`docs/tasks/2026-09-21-stage0-entrypoints.md` вместе с их разделами
результата — оттуда видно фактические имена функций; сам код в
`src/finplan/`.

На машине доступен Docker (демон через colima), плагина `docker compose`
нет; `testcontainers` работает через обычный Docker API и плагина не
требует.

## Задание

**`tests/conftest.py`.** Общие фикстуры уровня сессии:

- контейнер PostgreSQL 16 поднимается один раз на сессию pytest через
  `testcontainers`; строка подключения отдаётся фикстурой;
- фикстура применённых миграций: `alembic upgrade head` на этом контейнере
  выполняется один раз;
- фикстура сессии, которая откатывает состояние между тестами вложенной
  транзакцией (`SAVEPOINT`), не коммитящейся по завершении теста, — как
  требует раздел 11.1;
- фикстура окружения: минимальный набор переменных раздела 10.1, при котором
  `Settings` создаётся, с подстановкой строки подключения контейнера;
- тесты, требующие Docker, помечаются маркером `integration` и пропускаются
  с понятным сообщением, если Docker недоступен; модульные тесты обязаны
  проходить без Docker.

**`tests/unit/test_layering.py`.** Проверка направления зависимостей по
разделу 2.2 через разбор исходников модулем `ast`, а не по тексту строк:
обходятся все файлы `src/finplan/**/*.py`, из каждого собираются импорты
(`Import` и `ImportFrom`, включая относительные, приведённые к абсолютному
виду), и проверяются правила:

- `finplan.domain` не импортирует `finplan.application`,
  `finplan.infrastructure`, `finplan.entrypoints`, а также `sqlalchemy`,
  `aiogram`, `fastapi`, `pydantic_settings`, `redis`, `asyncpg`, `alembic`;
- `finplan.application` не импортирует `finplan.infrastructure` и
  `finplan.entrypoints`, а также `sqlalchemy`, `aiogram`, `fastapi`;
- `finplan.infrastructure` не импортирует `finplan.entrypoints`;
- нарушение даёт падение с сообщением, где назван файл, строка и запрещённый
  импорт; сообщения по всем нарушениям собираются в одно, а не падают на
  первом.

Тест обязан ловить нарушение, а не только проходить на текущем коде: добавить
к нему проверку самого анализатора на искусственном фрагменте кода (строка с
запрещённым импортом, разобранная тем же кодом), чтобы зелёный результат не
означал, что анализатор ничего не видит.

**`tests/integration/test_migrations.py`.** По разделу 11.5: на чистой базе
прогоняются `upgrade head`, затем `downgrade base`, затем снова
`upgrade head`; после первого `upgrade` проверяется, что таблицы `users` и
`currencies` существуют и справочник валют наполнен девятью строками; после
`downgrade base` — что обеих таблиц нет. Отдельный тест выполняет
`alembic check` и падает при расхождении схемы с метаданными SQLAlchemy.

**`tests/integration/api/test_health.py`.** Запрос `GET /health` через
`httpx.AsyncClient` с `ASGITransport` на приложении, собранном фабрикой:
ответ `200`, тело содержит признак успешной проверки БД, заголовок
`X-Request-ID` возвращается и совпадает с переданным.

**`tests/integration/bot/test_start.py`.** Хендлер `/start` вызывается на
искусственном апдейте (`aiogram` с подменённым Bot API либо прямой вызов
хендлера с объектом `Message`-заглушкой): проверяется, что ответ отправлен и
текст непуст. Обращений к сети нет.

Тест-заглушка, созданная в подзадаче каркаса сборки (если она есть),
удаляется: её роль закрыта настоящими тестами.

## Границы

- файлы в `src/finplan/`, `migrations/`, `alembic.ini`, `Makefile`,
  `pyproject.toml` не изменяются. Если тест не проходит из-за дефекта
  продуктового кода, дефект описывается в разделе «Вопросы диспетчеру» с
  указанием `file:line`, а не чинится здесь;
- исключение — `pyproject.toml`: если для тестов не хватает объявленной
  зависимости, она добавляется, и добавление называется в разделе
  результата;
- новые каталоги вне `tests/` из раздела 2.1 не создаются;
- `docs/architecture.md`, `CLAUDE.md`, `docs/dev-log.md` не изменяются;
- тесты на SQLite не пишутся: раздел 11.1 запрещает это прямо.

## Критерий приёмки

- `uv run pytest -m "not integration"` проходит без Docker;
- `uv run pytest` проходит целиком при доступном Docker; фактическая строка
  итога pytest приводится в разделе результата;
- `tests/unit/test_layering.py` содержит разбор через `ast` и проверку
  самого анализатора на искусственном нарушении;
- тест миграций выполняет все три шага цикла и проверяет содержимое
  `currencies` после первого `upgrade`;
- `uv run ruff check` и `uv run ruff format --check` проходят на каталоге
  `tests/`;
- `git status --short` показывает изменения только внутри `tests/` и, при
  необходимости, в `pyproject.toml` и `uv.lock`.

## Результат исполнителя

**Сделано.** Написаны тесты каркаса этапа 0: общие фикстуры, проверка правил
слоёв, цикл миграций, `GET /health`, `/start` бота. Готовой тест-заглушки из
подзадачи каркаса сборки в `tests/` не оказалось (там были только `.gitkeep`
в пустых каталогах) — удалять было нечего; `.gitkeep` в `tests/integration/api/`
и `tests/integration/bot/` убраны, так как в этих каталогах появились
настоящие файлы.

`tests/conftest.py` — общие фикстуры уровня сессии:
- `TESTCONTAINERS_RYUK_DISABLED=true` выставляется через `os.environ.setdefault`
  на уровне модуля. Находка: на этой машине Docker работает через colima, и
  Ryuk (реапер testcontainers) падает при старте с `error while creating
  mount source path '.../docker.sock': mkdir ...: operation not supported` —
  colima монтирует сокет иначе, чем host-путь, который Ryuk пытается
  примонтировать сам себе. Реапер не обязателен для корректности тестов:
  контейнер поднимается и останавливается явно через `with
  PostgresContainer(...) as container:` в фикстуре `postgres_container`.
  `setdefault` не переопределяет значение, если оно уже задано снаружи.
- Тот же модульный блок выставляет минимальный набор переменных раздела 10.1
  (`APP_ENV`, `APP_BASE_URL`, заглушечный `DATABASE_URL`, рабочую заглушку
  `TELEGRAM_BOT_TOKEN` из `.env.example`, `JWT_SECRETS`, `CORS_ORIGINS`) через
  `os.environ.setdefault` — находка: `entrypoints/api/app.py` и
  `entrypoints/bot/main.py` строят модульные объекты (`app = create_app()`,
  `bot = Bot(...)`) прямо при импорте модуля, то есть ещё на этапе сбора
  тестов pytest, до того как успевает отработать любая фикстура; без этого
  блока сам импорт тестового файла падал бы `ValidationError` от
  `pydantic-settings`.
- `postgres_container` (session) — `PostgresContainer("postgres:16-alpine",
  driver="asyncpg")` из `testcontainers.community.postgres` (не
  `testcontainers.postgres` — тот модуль в установленной версии
  `testcontainers` помечен `DeprecationWarning` и просто реэкспортирует
  `community.postgres`), поднимается один раз на сессию.
- `database_url`, `migrated_database` (session) — строка подключения и
  фикстура, один раз на сессию прогоняющая `alembic upgrade head` через
  `run_alembic` (см. ниже).
- `run_alembic(url, *args)` — запускает `uv run alembic <args>` в
  `subprocess.run` из корня репозитория с переменными раздела 10.1 и
  переданным `DATABASE_URL` в окружении подпроцесса; при ненулевом коде
  возврата поднимает `RuntimeError` с полными `stdout`/`stderr`. Через
  подпроцесс, а не через `alembic.command` в процессе: `migrations/env.py`
  сам вызывает `asyncio.run(...)` внутри `run_migrations_online()`, а тесты
  уже выполняются pytest-asyncio внутри работающего event loop — вложенный
  `asyncio.run` в том же потоке упал бы `RuntimeError: asyncio.run() cannot
  be called from a running event loop`.
- `alembic_runner` — фикстура-обёртка над `run_alembic` для файлов тестов:
  находка второго порядка — `tests/**` не образует Python-пакет (нет
  `__init__.py` нигде под `tests/`, раздел 2.1 дерева каталогов их не
  требует), и `from tests.conftest import run_alembic` в отдельном файле
  теста падает `ModuleNotFoundError: No module named 'tests'` под стандартным
  `--import-mode=prepend` pytest (rootpath для файла без `__init__.py` — его
  собственный каталог, не корень репозитория). Фикстура — устойчивый к
  режиму импорта способ передать общую функцию файлам тестов.
- `fresh_database_url` (function, async) — создаёт отдельную БД (`CREATE
  DATABASE test_migrations_<uuid>`) в том же контейнере через
  admin-подключение с `isolation_level="AUTOCOMMIT"` (`CREATE DATABASE`
  нельзя выполнить внутри транзакции), отдаёт готовый URL, затем удаляет
  базу (`DROP DATABASE ... WITH (FORCE)`). Нужна тесту цикла миграций: он
  обязан стартовать с абсолютно пустой схемы и не имеет права трогать базу,
  которой пользуются остальные интеграционные тесты.
- `env_vars` (function) — минимальный набор переменных раздела 10.1 с
  `DATABASE_URL`, подставленным на `migrated_database`, через
  `monkeypatch.setenv`; `get_settings.cache_clear()` вызывается до и после
  теста (`get_settings` — `lru_cache`, иначе следующий тест унаследовал бы
  настройки этого).
- `db_session` (function, async) — сессия SQLAlchemy на вложенной транзакции
  (`SAVEPOINT`), классический паттерн join-session-into-external-transaction,
  адаптированный под asyncio: `session.sync_session` слушает
  `after_transaction_end` и перезапускает `SAVEPOINT` после каждого
  `commit()`/`rollback()` внутри теста, внешняя транзакция соединения
  откатывается в `finally`. Фикстура написана по прямому требованию задания
  (раздел 11.1), но в этой подзадаче её никто не использует — репозиториев,
  которые бы её использовали, в проекте этапа 0 ещё нет.
- `pytest_collection_modifyitems` пропускает тесты с явным
  `pytest.mark.integration`, если `docker info` недоступен. Находка при
  ручной проверке: изначальная реализация проверяла `"integration" in
  item.keywords`, а не `item.get_closest_marker("integration")` — `keywords`
  в pytest включает и служебные ключевые слова, произведённые из компонентов
  пути узла (`tests`, `integration`, `bot`, ...) для `-k`, поэтому
  `tests/integration/bot/test_start.py` (без явного маркера, к Docker не
  обращается вообще) ошибочно пропускался бы вместе с тестами, которым Docker
  реально нужен. Исправлено на `get_closest_marker`; вручную проверено:
  без Docker в `PATH` (`docker info` недоступен) — `health`/`migrations`
  пропускаются с сообщением `Docker недоступен: тест требует
  testcontainers`, а оба теста `test_start.py` по-прежнему проходят.

`tests/unit/test_layering.py` — обход `src/finplan/**/*.py`, парсинг `ast`
(`Import`/`ImportFrom` с разрешением относительных импортов любого уровня
вложенности через `__package__`), сверка с правилами раздела 2.2
(`domain` не видит `application`/`infrastructure`/`entrypoints` и
`sqlalchemy`/`aiogram`/`fastapi`/`pydantic_settings`/`redis`/`asyncpg`/`alembic`;
`application` не видит `infrastructure`/`entrypoints` и
`sqlalchemy`/`aiogram`/`fastapi`; `infrastructure` не видит `entrypoints`).
Нарушения по всем файлам собираются в одно сообщение с `file:line` и
запрещённым импортом, не падают на первом. Три теста:
`test_layers_do_not_violate_dependency_direction` — сам продуктовый код
(зелёный: домен и application на этапе 0 — пустые пакеты, нарушать пока
нечем); `test_analyzer_detects_synthetic_violation` — искусственный
фрагмент с прямым (`import sqlalchemy`) и относительным (`from ..
import application as sibling`) нарушением, анализатор обязан найти оба;
`test_analyzer_passes_clean_synthetic_code` — контрольный отрицательный
пример (разрешённый импорт внутри `domain`), анализатор не должен ничего
находить. Ручная проверка вне автотеста: временно дописанный
`import sqlalchemy` в реальный `src/finplan/domain/common/__init__.py`
уронил `test_layers_do_not_violate_dependency_direction` с точным
`file:line`; после проверки файл возвращён к исходному пустому состоянию
(0 байт, как и остальные `__init__.py` в `domain/`).

`tests/integration/test_migrations.py` — два теста на `fresh_database_url`:
`test_migration_cycle_upgrade_downgrade_upgrade` прогоняет `upgrade head` →
`downgrade base` → `upgrade head` подряд без ручного вмешательства, после
первого `upgrade` проверяет наличие таблиц `users`/`currencies` через
`inspect(sync_conn).get_table_names()` и `SELECT count(*) FROM currencies` =
9, после `downgrade base` — отсутствие обеих таблиц, третий `upgrade`
проверяет, что цикл действительно замкнут; `test_alembic_check_matches_sqlalchemy_metadata`
прогоняет `upgrade head`, затем `alembic check` (падение — `RuntimeError` от
`run_alembic`/`alembic_runner` с полным выводом Alembic).

`tests/integration/api/test_health.py` — `create_app()` вызывается заново
в каждом тесте (а не переиспользуется модульный `app` из
`entrypoints/api/app.py`, который собирается один раз при самом импорте —
до того, как фикстура `env_vars` успевает подставить рабочий `DATABASE_URL`),
`lifespan` входится вручную через `app.router.lifespan_context(app)`, запрос
идёт через `httpx.ASGITransport`. Три теста: `200` с `database.ok is True`;
`X-Request-Id` без переданного значения генерируется и соответствует формату
ULID (регэксп `^[0-9A-HJKMNP-TV-Z]{26}$` из окружения задачи — сверх
буквального текста задания, которое требовало только непустой заголовок);
переданный `X-Request-Id` возвращается как есть. Ручная проверка вне
автотеста: `create_app()` с намеренно недоступной БД (несуществующий порт)
— `lifespan` действительно падает исключением при входе (`check_revision`
не может даже открыть соединение), то есть тест "database.ok is True" не
мог бы пройти случайно на нерабочей БД.

`tests/integration/bot/test_start.py` — раздел 11.3 называет инструментом
`aiogram.test_utils.mocked_bot.MockedBot`; в установленной версии `aiogram`
(3.31.0) пакета `aiogram.test_utils` нет вообще (найдено через `find` по
site-packages) — расхождение документа с фактической зависимостью, названо
в «Вопросах диспетчеру». Тест использует альтернативу, прямо разрешённую
текстом самого задания («вызывается на искусственном апдейте... либо прямой
вызов хендлера с объектом Message-заглушкой»): `FakeSession(BaseSession)`
перехватывает `SendMessage` на уровне HTTP-транспорта (том самом месте, где
aiogram сам ожидает подмену для тестов — `Bot(token=..., session=...)`) и
строит правдоподобный `Message`-ответ без обращения к `api.telegram.org`;
сама маршрутизация (`CommandStart`), `Dispatcher` и хендлер — настоящие,
апдейт прогоняется через `dispatcher.feed_update(bot, update)`. Два теста:
список сабраутеров диспетчера непуст и содержит `start`; `/start` даёт ровно
один `SendMessage` с непустым текстом в правильный чат. Находка при первом
прогоне: фикстура `dispatcher` не могла быть function-scoped — `start_router`
из `finplan.entrypoints.bot.routers.start` модульный объект-одиночка, и
повторный `include_router` того же объекта в другом `Dispatcher` — ошибка
aiogram (`RuntimeError: Router is already attached to ...`); исправлено на
`scope="module"`.

**Проверка.**
- `uv run pytest -m "not integration"` (Docker доступен, но выборка та же,
  что была бы без него) — `5 passed, 5 deselected in 1.68s`; отдельно
  проверено с реально недоступным Docker (`PATH` без каталога `docker`,
  `docker info` падает) — `5 passed, 5 skipped in 1.53s`, `-rs` показывает
  `SKIPPED [3] tests/integration/api/test_health.py: Docker недоступен: тест
  требует testcontainers` и `SKIPPED [2] tests/integration/test_migrations.py:
  Docker недоступен: тест требует testcontainers` — `tests/integration/bot/`
  в выборку пропусков не попал, оба его теста прошли и без Docker.
- `uv run pytest` (Docker доступен, контейнер поднимается через
  `testcontainers`) — фактическая итоговая строка: `10 passed in 6.03s`.
- `uv run ruff check tests/` — `All checks passed!`.
- `uv run ruff format --check tests/` — `5 files already formatted`.
- `uv run ruff check` (весь репозиторий) — `All checks passed!`.
- `uv run ruff format --check` (весь репозиторий) — `68 files already
  formatted`.
- `uv run mypy src` — `Success: no issues found in 53 source files`
  (каталог `tests/` вне `mypy_path`/`packages` конфигурации проекта — не
  проверяется этой командой, как и в предыдущих подзадачах).
- `git status --short` — все изменения этой подзадачи новые файлы под
  `tests/`; `pyproject.toml` и `uv.lock` не менялись — недостающих
  зависимостей для тестов не нашлось (`testcontainers[postgres]`,
  `pytest-asyncio`, `hypothesis` были объявлены заранее). Отдельно отмечу:
  весь остальной репозиторий (`src/`, `docs/`, `pyproject.toml` и т. д.) в
  git пока не отслеживается вообще (`git log` показывает только «Initial
  commit» с `.gitignore`/`LICENSE`/`README.md`) — коммитов предыдущих
  подзадач не было, это не изменение этой подзадачи, фиксирую как
  наблюдение.
- `docker ps -a` после всех проверок — работает только `finplan-pg`,
  контейнеры `testcontainers` не остались (поднимаются и останавливаются
  явным `with`-блоком за каждый прогон).

**Решения и отложенное.**
- `TESTCONTAINERS_RYUK_DISABLED=true` — не архитектурное решение, а обход
  конкретной несовместимости Ryuk с сокетом Docker под colima на этой
  машине; без него `PostgresContainer().start()` падает `APIError: 500
  Server Error ... error while creating mount source path
  '.../docker.sock'`. Задание прямо говорит, что плагина `docker compose`
  нет и `testcontainers` работает через обычный Docker API — про Ryuk и
  colima отдельно не сказано, решение принято по месту как чисто техническая
  находка, а не как расхождение с документом.
- Цикл миграций и `alembic check` идут через `subprocess` (`uv run
  alembic ...`), а не через `alembic.command` в процессе — единственный
  рабочий вариант: `migrations/env.py` сам делает `asyncio.run(...)`, а
  внутри теста pytest-asyncio уже держит открытый event loop; вложенный
  `asyncio.run` в том же потоке падает `RuntimeError`. Через `subprocess`
  плата — around ~1 секунда на вызов `alembic`, что не мешает набору из
  10 тестов оставаться быстрым (6 секунд целиком, с поднятием контейнера).
- Все async-фикстуры, кроме `postgres_container`/`database_url`/
  `migrated_database` (которые синхронные, контейнер и alembic-подпроцесс
  не требуют event loop), сделаны function-scoped, а не session-scoped:
  `pytest-asyncio` в режиме `asyncio_mode = "auto"` даёт каждому тесту
  собственный event loop по умолчанию, а session-scoped async-фикстура
  требует либо правки `asyncio_default_fixture_loop_scope` в
  `pyproject.toml` (граница задачи это не разрешает без явной нужды), либо
  `loop_scope="session"` на каждой фикстуре с риском рассинхронизации с
  function-scoped loop тестов. Function-scoped `engine`/`db_session` создают
  и закрывают пул соединений на каждый тест — стоимость незаметна на фоне
  самого поднятия контейнера.
- `db_session` (SAVEPOINT-фикстура) написана по прямому требованию раздела
  11.1 задания, но в этой подзадаче её не использует ни один тест —
  репозиториев, для которых она нужна, в кодовой базе этапа 0 ещё нет.
  Формально нет теста, который бы сам проверял корректность её отката;
  оставляю как инфраструктуру для следующих подзадач (репозитории `users`/
  `currencies` появятся не раньше этапа 1), называю осознанно, а не молчу.
- `tests/integration/bot/test_start.py` не помечен `pytest.mark.integration`,
  хотя лежит в каталоге `tests/integration/` (по пирамиде раздела 11.1
  хендлеры aiogram — интеграционный уровень с PostgreSQL/`MemoryStorage`).
  На этапе 0 хендлер `/start` не обращается ни к БД, ни к сети вообще (по
  прямому тексту задачи `entrypoints`: «Никаких обращений к базе... это
  этап 1») — маркер `integration` в этом файле означал бы искусственную
  зависимость от Docker там, где её по факту нет; проверено вручную, что
  без Docker оба теста файла всё равно проходят. Когда на следующих этапах
  хендлеры начнут писать в БД, соответствующие новые тесты в этом же файле
  или новых файлах того же каталога будут промаркированы `integration`
  осознанно.
- `.gitkeep` удалены только в `tests/integration/api/` и
  `tests/integration/bot/` (там появились настоящие файлы); в
  `tests/integration/repositories/`, `tests/unit/domain/`,
  `tests/unit/finance/`, `tests/e2e/` оставлены — эти уровни пирамиды в этой
  подзадаче не покрывались (репозиториев, доменных сущностей, формул и
  сквозных сценариев в проекте этапа 0 ещё нет).

**Вопросы диспетчеру.**

- Раздел 11.3 `docs/architecture.md` называет инструментом тестирования
  хендлеров aiogram `aiogram.test_utils.mocked_bot.MockedBot`. В
  установленной версии `aiogram` (`3.31.0`, зафиксирована в `uv.lock`)
  пакета `aiogram.test_utils` нет вообще — ни модуля, ни файла с похожим
  именем нигде в дистрибутиве. Похоже, это осталось от aiogram 2.x и не
  переехало в 3.x; либо нужна отдельная библиотека, либо документ описывает
  API, которого в used-версии не существует. Тест написан обходным путём,
  прямо разрешённым текстом задания (перехват на уровне `BaseSession`), но
  для последующих этапов (диалоги с состояниями FSM, раздел 11.3) стоит
  решить: обновлять ли раздел 11.3 документа под фактический API `aiogram`
  3.31, или закладывать в зависимости что-то другое для тестирования ботов.
