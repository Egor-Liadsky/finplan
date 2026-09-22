# Каркас сборки: pyproject, дерево пакетов, Makefile, .env.example

- **Исполнитель:** developer
- **Слой:** docs (инфраструктура репозитория, продуктового кода нет)
- **Раздел архитектуры:** docs/architecture.md, разделы 2.1, 10.2, 10.6, 11
- **Заведена:** 2026-09-21

## Входные условия

Репозиторий содержит только документацию: `docs/architecture.md`, `CLAUDE.md`,
`docs/tasks/README.md`, файлы агентов в `.claude/agents/`, `README.md`,
`LICENSE`, `.gitignore`. Продуктового кода, `pyproject.toml` и каталога `src/`
нет. Это первая подзадача этапа 0 «Каркас» из раздела 13 архитектуры.

На машине доступны `uv` версии 0.12 и `make` 3.81. Системный Python — 3.9,
поэтому интерпретатор 3.12 обязан приходить из `uv`, а не из системы.

Прочитать до первой правки: `docs/architecture.md`, разделы 2.1 «Дерево
каталогов», 2.2 «Правила слоёв», 10.2 «Файлы настроек», 10.6 «Команды
Makefile», 11 «Стратегия тестирования» (вводный абзац про покрытие и раздел
11.1); `docs/tasks/README.md` — формат раздела результата.

## Задание

Создать каркас сборки проекта.

**`pyproject.toml`.** Проект `finplan`, требование `requires-python = ">=3.12,<3.13"`,
раскладка `src`: пакет лежит в `src/finplan`. Сборочный бэкенд — `hatchling`.

Зависимости времени выполнения: `fastapi`, `uvicorn[standard]`, `aiogram`
версии 3, `sqlalchemy[asyncio]` версии 2.x, `asyncpg`, `alembic`, `pydantic`
версии 2, `pydantic-settings`, `structlog`, `redis`, `apscheduler`, `httpx`.
Группа зависимостей разработки (`[dependency-groups] dev`): `pytest`,
`pytest-asyncio`, `ruff`, `mypy`, `coverage[toml]`, `hypothesis`,
`testcontainers[postgres]`. Верхние границы версий не закреплять: фиксация —
задача `uv.lock`.

Настройки инструментов в том же файле:

- `ruff` — длина строки 100, включены правила как минимум `E`, `F`, `I`, `UP`,
  `B`, `N`, `RUF`; `ruff format` настроек по умолчанию достаточно;
- `mypy` — база нестрогая, но для пакетов `finplan.domain.*` и
  `finplan.application.*` включён `strict = true` через секцию `[[tool.mypy.overrides]]`;
  `mypy_path = "src"`, `packages = ["finplan"]` или эквивалент, чтобы работала
  команда `uv run mypy src`;
- `pytest` — `testpaths = ["tests"]`, `asyncio_mode = "auto"`, маркеры
  `unit`, `integration`, `e2e` объявлены в `markers`;
- `coverage` — источник `src/finplan`, отчёт с `show_missing`.

**Дерево пакетов.** Создать каталоги из раздела 2.1 под `src/finplan/` как
пакеты Python: в каждом каталоге — `__init__.py`. Файл `src/finplan/py.typed`
создать пустым. Каталоги: `domain/{common,entities,finance,services}`,
`application/{dto,ports,use_cases}` и подкаталоги `use_cases/{transactions,
accounts,categories,budgets,goals,deposits,reports,auth,scheduling}`,
`infrastructure/{db,db/models,db/repositories,db/queries,cache,fx,telegram,security}`,
`entrypoints/{api,api/schemas,api/routers,bot,bot/middlewares,bot/keyboards,
bot/parsers,bot/formatters,bot/routers,worker,worker/jobs,cli}`.

Пустых модулей-заглушек по именам файлов из раздела 2.1 (`money.py`,
`xirr.py`, `transaction.py` и прочих) **не создавать**: эти файлы появляются
на этапах 1 и дальше вместе с кодом. Каталог не считается пустым, потому что
в нём лежит `__init__.py`.

Каталог `tests/` создать по разделу 2.1: `tests/unit/{finance,domain}`,
`tests/integration/{repositories,api,bot}`, `tests/e2e/`. Файлы тестов и
`tests/conftest.py` в этой подзадаче не пишутся — это отдельная подзадача.
Чтобы каталоги попали в git, положить в каждый пустой каталог тестов файл
`.gitkeep`.

Каталог `frontend/` в этой подзадаче не создаётся: SPA относится к этапу 2.

**`Makefile`.** Команды раздела 10.6: `up`, `migrate`, `revision`, `seed`,
`test`, `lint`, `recalc`. Обязаны работать уже сейчас: `test` — `uv run pytest`,
`lint` — последовательно `uv run ruff check`, `uv run ruff format --check`,
`uv run mypy src`. Команды `migrate` (`uv run alembic upgrade head`),
`revision` (`uv run alembic revision --autogenerate -m "$(m)"`) и `up`
(`docker compose up -d`) записать полностью, хотя их инструменты появятся в
следующих подзадачах. Команды `seed` и `recalc` — заглушка, печатающая
`not implemented yet: stage 1` и завершающаяся кодом 0. Все цели объявить в
`.PHONY`.

**`.env.example`.** Полный перечень переменных из таблицы раздела 10.1 —
все тридцать с лишним строк, в том же порядке, с безопасными значениями-заглушками:
настоящих токенов и секретов в файле нет. Обязательные переменные заполнены
работающими локальными значениями (`DATABASE_URL` указывает на
`postgresql+asyncpg://finplan:finplan@localhost:5432/finplan` — реквизиты из
раздела 10.3), секреты — очевидными заглушками вроде `changeme`. Каждую
переменную снабдить коротким комментарием, если её назначение не следует из
имени.

**`uv.lock`.** Зафиксировать командой `uv sync`, файл коммитится.

## Границы

- каталоги вне дерева раздела 2.1 `docs/architecture.md` не создаются;
- `docs/architecture.md`, `CLAUDE.md`, `docs/dev-log.md` и файлы в
  `.claude/` не изменяются;
- `src/finplan/config.py`, `logging.py`, `container.py` в этой подзадаче не
  пишутся: это следующая подзадача;
- `alembic.ini`, `migrations/`, `Dockerfile`, `docker-compose.yml`,
  `.github/` в этой подзадаче не создаются;
- код в `src/finplan/**` кроме `__init__.py` и `py.typed` не появляется;
- версии зависимостей не прибиваются к точным значениям в `pyproject.toml`.

## Критерий приёмки

- `uv sync` проходит и создаёт `uv.lock`; в окружении Python 3.12;
- `uv run python -c "import finplan; print(finplan.__file__)"` печатает путь
  внутри `src/finplan`;
- `uv run ruff check` и `uv run ruff format --check` проходят без находок;
- `uv run mypy src` проходит без ошибок;
- `make lint` и `make test` выполняются; `make test` завершается успешно при
  нулевом числе собранных тестов (`pytest` с пустым `tests/` возвращает код 5 —
  обеспечить, чтобы цель `test` при этом не считалась провалившейся, либо
  положить в `tests/` минимальный проходящий тест-заглушку `tests/unit/test_smoke.py`;
  выбранный вариант назвать в разделе результата);
- `find src/finplan -type d -empty` и `find tests -type d -empty` не выводят
  ничего;
- `.env.example` содержит все имена переменных из таблицы раздела 10.1
  архитектуры: проверяется тем, что для каждого имени из таблицы в файле есть
  строка, начинающаяся с этого имени и знака `=`;
- `git status --short` не показывает файлов вне `pyproject.toml`, `uv.lock`,
  `Makefile`, `.env.example`, `src/`, `tests/`.

## Результат исполнителя

**Сделано.** Создан каркас сборки проекта: `pyproject.toml` с раскладкой
`src`, сборочным бэкендом `hatchling`, полным списком рантайм-зависимостей и
группой `dev` из задания, настройками `ruff` (длина строки 100, правила
`E, F, I, UP, B, N, RUF`), `mypy` (нестрогая база, `strict = true` через
`[[tool.mypy.overrides]]` для `finplan.domain.*` и `finplan.application.*`,
`mypy_path = "src"`, `packages = ["finplan"]`), `pytest` (`testpaths =
["tests"]`, `asyncio_mode = "auto"`, маркеры `unit`/`integration`/`e2e`) и
`coverage` (`source = ["src/finplan"]`, `show_missing = true`). Под
`src/finplan/` разложено дерево пакетов из раздела 2.1 архитектуры — во всех
41 каталоге лежит пустой `__init__.py`, плюс пустой `src/finplan/py.typed`;
модули-заглушки внутри пакетов не создавались. Каталог `tests/` разложен по
тому же разделу (`unit/{finance,domain}`, `integration/{repositories,api,
bot}`, `e2e/`), во все пустые каталоги положен `.gitkeep`; сами тесты и
`conftest.py` не писались. Добавлен `Makefile` с целями `up`, `migrate`,
`revision`, `seed`, `test`, `lint`, `recalc`, все объявлены в `.PHONY`.
Добавлен `.env.example` со всеми 28 переменными из таблицы раздела 10.1 в
том же порядке, с безопасными заглушками и краткими комментариями там, где
назначение не следует из имени. Зафиксирован `uv.lock` командой `uv sync`
(окружение — Python 3.12.14).

Отдельное техническое решение: `ruff` версии 0.16.8 по умолчанию включает
`*.md` в файлы для `ruff format` и форматирует встроенные в markdown блоки
кода Python — без исключения `uv run ruff format --check` пытался бы
переформатировать блоки кода aiogram-диалогов внутри `docs/architecture.md`,
который править нельзя. Добавлена строка `extend-exclude = ["docs"]` в
`[tool.ruff]`, чтобы каталог `docs/` не участвовал в проверках `ruff`; на
`ruff check`/`mypy` это не влияет, так как python-кода в `docs/` нет.

**Проверка.**
- `uv sync` — успешно, создан/обновлён `uv.lock`, `uv run python --version`
  → `Python 3.12.14`.
- `uv run python -c "import finplan; print(finplan.__file__)"` — успешно,
  печатает `/Users/egor_lyadskiy/finplan/src/finplan/__init__.py`.
- `uv run ruff check` — `All checks passed!`.
- `uv run ruff format --check` — `49 files already formatted`.
- `uv run mypy src` — `Success: no issues found in 41 source files`.
- `make lint` — успешно, все три шага (`ruff check`, `ruff format --check`,
  `mypy src`) прошли.
- `make test` — успешно завершается кодом 0 при пустом `tests/`: `uv run
  pytest` внутри цели возвращает 5 (`no tests ran`), Makefile перехватывает
  этот код явной проверкой `if [ $$code -eq 5 ]` и превращает его в 0 с
  сообщением `no tests collected yet, treating as success`. Выбран этот
  вариант, а не `tests/unit/test_smoke.py`, потому что задание прямо
  запрещает писать файлы тестов в этой подзадаче.
- `find src/finplan -type d -empty` и `find tests -type d -empty` — пустой
  вывод у обеих команд.
- Перебор всех 28 имён переменных из таблицы раздела 10.1 — для каждого в
  `.env.example` есть строка вида `ИМЯ=...`; проверено скриптом, все имена
  найдены.
- `git status --short` — untracked только `pyproject.toml`, `uv.lock`,
  `Makefile`, `.env.example`, `src/`, `tests/`; `.claude/`, `CLAUDE.md`,
  `docs/` были untracked уже во входном состоянии репозитория и этой
  подзадачей не создавались и не менялись.

**Решения и отложенное.**
- `requires-python = ">=3.12,<3.13"` и жёсткая верхняя граница у
  `aiogram (>=3,<4)`, `sqlalchemy[asyncio] (>=2,<3)`, `pydantic (>=2,<3)` —
  единственные версии, закреплённые в `pyproject.toml`: это ограничения по
  мажорной версии из самого задания, а не фиксация точных версий, которую
  задание относит к `uv.lock`. Остальные зависимости — без верхней границы.
- Цель `make test` перехватывает код возврата 5 самим Makefile, а не
  настройкой `pytest` (`empty_parameter_set_mark` и подобные опции на этот
  код не влияют, штатного способа поменять поведение через
  `[tool.pytest.ini_options]` нет); решение локально к Makefile и не
  затрагивает конфигурацию pytest.
- `tool.ruff.extend-exclude = ["docs"]` добавлено как техническая настройка
  инструмента, а не архитектурное решение: она не меняет код, только не даёт
  `ruff format` трогать `docs/architecture.md`, который менять запрещено.
  Если диспетчер сочтёт более уместным точечно исключить сам файл
  (`docs/architecture.md`) вместо всего каталога `docs/`, это тривиальная
  правка одной строки.
- Каталоги вне дерева раздела 2.1 не создавались; `frontend/`,
  `alembic.ini`, `migrations/`, `Dockerfile`, `docker-compose.yml`,
  `.github/`, `config.py`, `logging.py`, `container.py` и любой код в
  `src/finplan/**` кроме `__init__.py`/`py.typed` осознанно не тронуты — по
  границам задания.

**Вопросы диспетчеру.**

Нет.
