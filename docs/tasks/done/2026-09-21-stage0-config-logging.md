# Конфигурация и логирование: config.py и logging.py

- **Исполнитель:** developer
- **Слой:** infrastructure (модули уровня пакета `finplan`, вне слоёв домена)
- **Раздел архитектуры:** docs/architecture.md, разделы 10.1, 10.2, 12.1
- **Заведена:** 2026-09-21

## Входные условия

Готова подзадача «Каркас сборки»: есть `pyproject.toml` с зависимостями
(`pydantic`, `pydantic-settings`, `structlog` уже в списке), `uv.lock`,
дерево пакетов `src/finplan/` с `__init__.py` и `py.typed`, `Makefile`,
`.env.example` с полным перечнем переменных раздела 10.1.

Прочитать до первой правки: `docs/architecture.md`, разделы 10.1 «Переменные
окружения», 10.2 «Файлы настроек», 12.1 «Логирование», 10.5 «Режим бота»
(там условие обязательности вебхучных переменных); `.env.example` — имена и
значения-заглушки должны совпасть с тем, что читает `Settings`;
`docs/tasks/README.md` — формат раздела результата; результат подзадачи
`docs/tasks/2026-09-21-stage0-build-skeleton.md` — что уже создано.

## Задание

**`src/finplan/config.py`.** Класс `Settings` на `pydantic-settings`,
читающий переменные таблицы раздела 10.1 — все, без пропусков, с указанными в
таблице значениями по умолчанию и признаками обязательности.

Структура — вложенные секции там, где префикс имени переменной естественно
выделяет группу: `app` (`APP_ENV`, `APP_DEBUG`, `APP_BASE_URL`), `log`
(`LOG_LEVEL`, `LOG_FORMAT`), `database` (`DATABASE_URL`, `DATABASE_POOL_SIZE`,
`DATABASE_MAX_OVERFLOW`, `DATABASE_ECHO`, `WORKER_DATABASE_URL`), `telegram`
(`TELEGRAM_*`), `jwt` (`JWT_SECRETS`, `JWT_ACCESS_TTL`), `fx` (`FX_PROVIDER`,
`FX_FETCH_CRON`). Переменные, не входящие ни в одну группу (`REDIS_URL`,
`REFRESH_TTL`, `LOGIN_TICKET_TTL`, `CORS_ORIGINS`, `DEFAULT_BASE_CURRENCY`,
`DEFAULT_TIMEZONE`, `SCHEDULER_ENABLED`, `SENTRY_DSN`), — поля верхнего
уровня. Имена переменных окружения обязаны совпадать с таблицей 10.1
дословно; вложенность — деталь класса, а не окружения.

Требования к поведению:

- отсутствие обязательной переменной (`APP_ENV`, `APP_BASE_URL`,
  `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `JWT_SECRETS`, `CORS_ORIGINS`)
  приводит к `ValidationError` при создании `Settings`, а не к значению по
  умолчанию;
- `TELEGRAM_BOT_TOKEN`, `JWT_SECRETS` и `DATABASE_URL` — `SecretStr`,
  значение не попадает в `repr` и в логи; для `DATABASE_URL` предусмотреть
  метод или свойство, отдающее строку подключения коду, которому она нужна;
- `WORKER_DATABASE_URL` при отсутствии равен `DATABASE_URL`;
- `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_WEBHOOK_PATH`, `TELEGRAM_WEBHOOK_SECRET`
  обязательны только при `TELEGRAM_MODE=webhook`: проверка через валидатор
  модели, сообщение об ошибке называет недостающую переменную;
- `APP_ENV` ограничен значениями `local`, `staging`, `production`;
  `LOG_FORMAT` — `json` или `console`; `TELEGRAM_MODE` — `polling` или
  `webhook`; `FX_PROVIDER` — `cbr` или `none`. Реализуются как `Literal` или
  `StrEnum`;
- `JWT_SECRETS` и `CORS_ORIGINS` — списки, разбираемые из строки через
  запятую; пустой список считается ошибкой;
- чтение `.env` включено для локального запуска, регистр имён переменных не
  важен, лишние переменные окружения не ломают разбор;
- функция-точка доступа `get_settings()` с кэшированием
  (`functools.lru_cache`), чтобы окружение читалось один раз за процесс.

**`src/finplan/logging.py`.** Настройка `structlog` функцией
`configure_logging(settings)` (или принимающей уровень и формат явно):

- формат выбирается `LOG_FORMAT`: `json` — `structlog.processors.JSONRenderer`,
  `console` — `ConsoleRenderer` с цветом;
- уровень берётся из `LOG_LEVEL`; стандартный `logging` подключён к тому же
  конвейеру, чтобы логи `uvicorn`, `sqlalchemy` и `aiogram` шли тем же
  форматом;
- в каждой записи есть отметка времени в ISO 8601 UTC, уровень и имя
  логгера;
- контекст `request_id` и `user_id` переносится через
  `structlog.contextvars`: предусмотреть функции привязки и очистки
  контекста, чтобы точки входа проставляли их на входящий запрос или
  апдейт. Сами точки входа в этой подзадаче не правятся;
- секреты не логируются: значения `SecretStr` в конвейер не попадают.

Публичные функции обоих модулей снабдить аннотациями типов: `mypy` над
`src` проходит, хотя строгий режим включён только для `domain` и
`application`.

## Границы

- правятся и создаются только `src/finplan/config.py` и
  `src/finplan/logging.py`;
- `pyproject.toml` изменяется только при необходимости добавить недостающую
  зависимость, и такое добавление называется в разделе результата;
- `.env.example` не переписывается: если обнаружено расхождение между ним и
  разбираемыми переменными, оно описывается в разделе «Вопросы диспетчеру»;
- `container.py` в этой подзадаче не создаётся;
- `entrypoints/**`, `infrastructure/**`, `domain/**`, `application/**` не
  изменяются;
- `docs/architecture.md`, `CLAUDE.md`, `docs/dev-log.md` не изменяются;
- новых каталогов не появляется.

## Критерий приёмки

- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src`
  проходят;
- при окружении, где заданы все обязательные переменные (значения можно взять
  из `.env.example`), `uv run python -c "from finplan.config import get_settings; s=get_settings(); print(s.app.env)"`
  печатает окружение и не падает;
- при удалении из окружения `DATABASE_URL` тот же вызов падает с
  `ValidationError`, и в сообщении названа переменная `DATABASE_URL`;
- `repr(get_settings())` не содержит подстроки из `TELEGRAM_BOT_TOKEN`:
  проверяется запуском с заведомо уникальным значением токена;
- при `TELEGRAM_MODE=webhook` и пустом `TELEGRAM_WEBHOOK_URL` создание
  `Settings` падает с сообщением, называющим `TELEGRAM_WEBHOOK_URL`;
- `configure_logging` с `LOG_FORMAT=json` даёт запись, которая разбирается
  `json.loads` и содержит ключи уровня, времени и сообщения; с
  `LOG_FORMAT=console` — человекочитаемую строку. Проверяется коротким
  запуском через `uv run python -c ...`, вывод приводится в разделе
  результата;
- запись, сделанная после привязки контекста, содержит `request_id` и
  `user_id`.

## Результат исполнителя

**Сделано.** Написаны `src/finplan/config.py` и `src/finplan/logging.py`.

`config.py`: класс `Settings` на `pydantic-settings` со всеми 28
переменными таблицы 10.1. Каждая секция (`AppSettings`, `LogSettings`,
`DatabaseSettings`, `TelegramSettings`, `JwtSettings`, `FxSettings`) сделана
отдельным `BaseSettings` с полями через `Field(validation_alias="ИМЯ_ПЕРЕМЕННОЙ")`
и подключена к `Settings` как `Field(default_factory=СекцияSettings)` —
единственный найденный рабочий способ добиться того, чтобы имена
переменных окружения совпадали с таблицей 10.1 дословно при вложенной
структуре класса: у `pydantic-settings` нет штатного варианта смешивать
плоские (без общего префикса секции) имена переменных с одним
`env_nested_delimiter`, поэтому вложенность реализована через независимые
`BaseSettings`-секции, а не через `BaseModel`-подмодели с ручным разбором.
Переменные без естественной группы (`REDIS_URL`, `REFRESH_TTL`,
`LOGIN_TICKET_TTL`, `CORS_ORIGINS`, `DEFAULT_BASE_CURRENCY`,
`DEFAULT_TIMEZONE`, `SCHEDULER_ENABLED`, `SENTRY_DSN`) — поля верхнего
уровня `Settings`. `TELEGRAM_BOT_TOKEN`, `JWT_SECRETS` (список
`SecretStr`) и `DATABASE_URL` — `SecretStr`/`list[SecretStr]`, наружу
строка подключения отдаётся методами `DatabaseSettings.dsn()` /
`.worker_dsn()`, первый JWT-секрет — методом `JwtSettings.signing_secret()`.
`WORKER_DATABASE_URL` при отсутствии равен `DATABASE_URL` через
`model_validator(mode="after")`. Условная обязательность
`TELEGRAM_WEBHOOK_URL`/`_PATH`/`_SECRET` при `TELEGRAM_MODE=webhook`
проверяется `model_validator(mode="after")` в `TelegramSettings`, сообщение
об ошибке называет конкретную недостающую переменную. `APP_ENV`,
`LOG_FORMAT`, `TELEGRAM_MODE`, `FX_PROVIDER` — `Literal`. `JWT_SECRETS` и
`CORS_ORIGINS` разбираются из строки через запятую полем с аннотацией
`Annotated[list[...], NoDecode]` и `field_validator(mode="before")` (без
`NoDecode` `pydantic-settings` пытается сначала распарсить значение как
JSON и падает раньше пользовательской валидации); пустой список — ошибка
с явным именем переменной. Чтение `.env` включено на каждой секции
(`env_file=".env"`), регистр не важен (`case_sensitive=False`), лишние
переменные не мешают разбору. `get_settings()` кэширует результат через
`functools.lru_cache(maxsize=1)`.

`logging.py`: `configure_logging(settings)` строит `structlog` через
`structlog.stdlib.ProcessorFormatter`, подключая стандартный `logging` к
тому же конвейеру процессоров (`merge_contextvars`, `add_logger_name`,
`add_log_level`, `TimeStamper(fmt="iso", utc=True)`,
`StackInfoRenderer`, `format_exc_info`, `UnicodeDecoder`, и собственный
`_redact_secrets`, заменяющий `SecretStr`/`SecretBytes` на `"***"`, если
они попадут в событие) — записи `uvicorn`, `sqlalchemy` и `aiogram` идут
тем же форматтером и тем же рендерером. Рендерер выбирается по
`LOG_FORMAT`: `json` → `JSONRenderer`, `console` → цветной
`ConsoleRenderer`. Уровень — из `LOG_LEVEL` через `getattr(logging, ...)`.
`bind_context(**fields)` и `clear_context()` оборачивают
`structlog.contextvars.bind_contextvars`/`clear_contextvars` — вызывающий
код (будущие `entrypoints`) передаёт `request_id`, `user_id` и любые
другие поля (например, `run_id` фоновых задач) произвольными
keyword-аргументами; точки входа этой подзадачей не правились.
Добавлен `get_logger(name)` — тонкая типизированная обёртка над
`structlog.get_logger`, нужна была, чтобы `mypy` не сообщал `Returning
Any`.

**Проверка.**
- `uv run ruff check` — `All checks passed!`.
- `uv run ruff format --check` — `51 files already formatted`.
- `uv run mypy src` — `Success: no issues found in 43 source files`.
- `make lint` — все три шага прошли (тот же результат, что выше).
- `make test` — `no tests collected yet, treating as success` (нулевой
  сбор тестов не считается провалом — поведение цели `test` из
  предыдущей подзадачи, тестов этой подзадачей не добавлялось).
- `uv run python -c "from finplan.config import get_settings; s=get_settings(); print(s.app.env)"`
  с полным окружением из `.env.example` — печатает `local`, не падает.
- Удаление `DATABASE_URL` из окружения → тот же вызов падает
  `pydantic_core._pydantic_core.ValidationError: 1 validation error for
  DatabaseSettings\nDATABASE_URL\n  Field required [type=missing, ...]`.
- `TELEGRAM_BOT_TOKEN=UNIQUE_ACCEPTANCE_TOKEN_555` (заведомо уникальное
  значение) → `'UNIQUE_ACCEPTANCE_TOKEN_555' in repr(get_settings())` —
  `False`.
- `TELEGRAM_MODE=webhook` без `TELEGRAM_WEBHOOK_URL` → падает
  `ValidationError: 1 validation error for TelegramSettings\n  Value
  error, TELEGRAM_WEBHOOK_URL is required when TELEGRAM_MODE=webhook`.
- `configure_logging` с `LOG_FORMAT=json`: запись
  `{"event": "checked", "request_id": "req-777", "user_id": "user-42",
  "logger": "finplan.acceptance", "level": "info", "timestamp":
  "2026-09-21T14:22:56.707759Z"}` — разбирается `json.loads`, содержит
  `timestamp`/`level`/`event`/`logger`/`request_id`/`user_id`.
- `configure_logging` с `LOG_FORMAT=console`: строка вида
  `2026-09-21T14:22:56.845287Z [info     ] human_readable_check
  [finplan.acceptance]` (с ANSI-цветом в реальном выводе) — человекочитаема.
- Запись после `bind_context(request_id=..., user_id=...)` содержит оба
  поля в обоих форматах; после `clear_context()` — не содержит. Проверено
  отдельным запуском (см. выше, JSON-пример), для console — отдельной
  парой записей до/после `clear_context()`.
- Все проверки из раздела «Критерий приёмки» прогонялись через
  `uv run --project ...` во временных каталогах вне репозитория со своим
  `.env`, скопированным из `.env.example`; после прогона временные
  каталоги удалены, `git status --short` в репозитории не показывает
  ничего лишнего.

**Решения и отложенное.**
- Технический найденный факт: правило `ruff` `RUF002` (`Docstring
  contains ambiguous <cyrillic letter>`) срабатывает на **любой** докстринг,
  где есть русский текст и хотя бы одно упоминание латинского идентификатора
  в обратных кавычках (например, `` `Settings` ``) — воспроизведено
  изолированным примером вне продуктового кода. В `config.py` докстринги
  действительно смешивают русский текст с именами вроде `` ``Settings`` ``,
  поэтому файл открывается директивой `# ruff: noqa: RUF002, RUF003` —
  это подавление в границах самого файла, `pyproject.toml` не тронут. В
  `logging.py` докстринги эту комбинацию не создают, там директива не
  понадобилась и была убрана (ruff сообщал `RUF100 Unused noqa`).
- Секции `Settings` реализованы как самостоятельные `BaseSettings` вместо
  `BaseModel`-подмоделей с `env_nested_delimiter`, потому что второй
  вариант требует единого префикса+разделителя для всех вложенных полей
  (`APP__ENV` и т.п.), а задание прямо требует имена переменных без
  какой-либо вложенности в самом имени (`APP_ENV`, не `APP__ENV`). Опробовано
  и отклонено на этапе эксперимента.
- Строки `default_factory=AppSettings` и т.п., а также вызов `Settings()`
  внутри `get_settings()`, помечены `# type: ignore[arg-type]` /
  `# type: ignore[call-arg]`: `mypy` (через `dataclass_transform` у
  `pydantic.BaseModel`) синтезирует сигнатуру конструктора по объявленным
  полям и не знает, что `pydantic-settings` заполняет обязательные поля из
  окружения при вызове без аргументов — вызов без аргументов при этом
  реально корректен и проверен рантайм-тестами выше. Точечное подавление
  выбрано вместо смены модели данных, поскольку сама модель (секции без
  значений по умолчанию для обязательных переменных) — прямое требование
  задания.
- `service` (`api`/`bot`/`worker`) из обязательных полей записи журнала
  (раздел 12.1 архитектуры) в `configure_logging` не добавлялся: это поле
  зависит от процесса и по заданию подзадачи точки входа не правятся —
  привязка `service` через `bind_context(service=...)` остаётся для
  подзадачи, которая пишет сами `entrypoints`.
- `StrEnum` не использовался для `AppEnv`/`LogFormat`/`TelegramMode`/
  `FxProvider` — задание допускает `Literal` или `StrEnum` равноправно,
  выбран `Literal` как более короткий вариант без дополнительного класса.

**Вопросы диспетчеру.**

Найдено расхождение уровня инструментов, не архитектуры: правило `ruff`
`RUF002`/`RUF003` (неоднозначные символы кириллицы) конфликтует с самим
стилем документа — русская проза, вперемешку с обратными кавычками вокруг
латинских идентификаторов, — который требуют и `docs/architecture.md`, и
`CLAUDE.md`. Оно будет срабатывать на **каждом** будущем файле с русским
докстрингом, упоминающим код (не только в этой подзадаче). Сейчас это
закрыто локальной директивой `# ruff: noqa: RUF002, RUF003` в начале
`config.py` — правки `pyproject.toml` не делал, так как это вне границ
задания. Стоит рассмотреть добавление `ignore = ["RUF001", "RUF002",
"RUF003"]` в `[tool.ruff.lint]` на уровне проекта, чтобы следующим
исполнителям не приходилось точечно тушить то же самое в каждом новом
файле — но это решение о конфигурации инструмента, а не мой вызов.
