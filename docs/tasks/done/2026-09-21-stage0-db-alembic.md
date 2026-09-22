# Инфраструктура БД: engine, base, Alembic и первая миграция

- **Исполнитель:** developer
- **Слой:** infrastructure
- **Раздел архитектуры:** docs/architecture.md, разделы 4.1, 4.3, 10.2, 10.4
- **Заведена:** 2026-09-21

## Входные условия

Готовы подзадачи «Каркас сборки» и «Конфигурация и логирование»: есть
`pyproject.toml` с `sqlalchemy[asyncio]`, `asyncpg`, `alembic`; дерево
пакетов `src/finplan/` с `infrastructure/db/` и `infrastructure/db/models/`;
`src/finplan/config.py` с `Settings` и `get_settings()`, где `DATABASE_URL`
— `SecretStr` со способом получить строку подключения.

Прочитать до первой правки: `docs/architecture.md`, разделы 4.1 «Общие
соглашения», 4.3 «Таблицы» — подразделы `users` и `currencies` целиком,
10.2 «Файлы настроек», 10.4 «Миграции при старте», 2.1 — расположение
`migrations/` и `infrastructure/db/`; `src/finplan/config.py` — как читать
настройки; `docs/tasks/README.md` — формат раздела результата.

На машине доступен Docker (демон через colima), плагина `docker compose`
нет. PostgreSQL для проверки поднимается командой `docker run`, например
`docker run -d --name finplan-pg -e POSTGRES_DB=finplan -e POSTGRES_USER=finplan
-e POSTGRES_PASSWORD=finplan -p 5432:5432 postgres:16-alpine`. Контейнер
после проверки останавливается и удаляется.

## Задание

**`src/finplan/infrastructure/db/base.py`.** Класс `Base` на
`sqlalchemy.orm.DeclarativeBase` с `MetaData`, где задан
`naming_convention` по разделу 4.1 дословно: `pk_%(table_name)s`,
`fk_%(table_name)s_%(column_0_name)s`, `uq_%(table_name)s_%(column_0_N_name)s`,
`ck_%(table_name)s_%(constraint_name)s`, `ix_%(table_name)s_%(column_0_N_name)s`.

**`src/finplan/infrastructure/db/engine.py`.** Фабрики async engine и
sessionmaker поверх `asyncpg`: параметры пула берутся из `Settings`
(`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_ECHO`). Функции
принимают настройки или строку подключения аргументом, а не читают окружение
сами — так их можно подменить в тестах. `async_sessionmaker` настроить с
`expire_on_commit=False`.

**ORM-модели `users` и `currencies`** в `infrastructure/db/models/`: по файлу
на таблицу, столбцы и ограничения — по разделу 4.3 дословно, включая типы
(`char(3)` для кода валюты, `timestamptz` для меток времени, `numeric` здесь
не встречается), значения по умолчанию, `NOT NULL`, уникальность
`telegram_id`, внешний ключ `users.base_currency` → `currencies.code`,
`CHECK` на `currencies.minor_unit` в диапазоне 0..4. Перечислений в этих
двух таблицах нет, но правило «`text` + `CHECK`, не нативный `ENUM`»
соблюдается и дальше. Питоновское значение по умолчанию для `users.id`
не задавать: UUIDv7 генерирует приложение, и генератор появится на этапе 1
вместе с доменными сущностями. Модели импортируются в
`infrastructure/db/models/__init__.py`, чтобы метаданные собирались одним
импортом.

**`alembic.ini`** в корне репозитория: `script_location = migrations`,
строка подключения в ini **не записывается** — раздел 10.2 требует читать её
из окружения в `env.py`. Настроить шаблон имени файла ревизии так, чтобы в
имя входили дата и слаг.

**`migrations/env.py`**: async-вариант, строка подключения берётся из
`Settings`, `target_metadata` — `Base.metadata` с импортом моделей,
`compare_type=True`, `render_as_batch` не нужен. Режим offline поддержать.

**Первая миграция** в `migrations/versions/`: создаёт `currencies` и `users`
именно в этом порядке (внешний ключ), наполняет `currencies` строками `RUB`,
`USD`, `EUR`, `CNY`, `KZT`, `GEL`, `TRY`, `AED`, `RSD` с названием, символом
там, где он общепринят, и `minor_unit` (для всех перечисленных — 2).
`downgrade` рабочий: удаляет обе таблицы в обратном порядке. Имена
ограничений в миграции обязаны получиться по соглашению из 4.1 — проверить
по фактическому DDL в базе, а не на глаз.

**Проверка ревизии при старте.** Раздел 10.4 требует, чтобы приложение
сравнивало ревизию в `alembic_version` с `head` из кода и отказывалось
стартовать при расхождении. Написать для этого функцию в
`infrastructure/db/` (имя и файл выбрать по смыслу; например,
`infrastructure/db/revision.py` — новый файл внутри существующего каталога
допустим), которая принимает соединение или сессию, возвращает обе ревизии и
поднимает исключение при расхождении. Вызов этой функции из точек входа —
следующая подзадача; здесь она только пишется и покрывается ручной проверкой.

## Границы

- `src/finplan/config.py` и `logging.py` не переписываются; нехватку в них
  чего-либо описать в разделе «Вопросы диспетчеру»;
- `domain/**`, `application/**`, `entrypoints/**` не изменяются;
- таблицы, кроме `users` и `currencies`, не создаются: остальные семнадцать
  таблиц раздела 4.3 относятся к этапам 1 и дальше;
- Row Level Security в этой миграции не включается — она относится к разделу
  4.5 и этапу 1, когда появятся пользовательские данные;
- `Dockerfile`, `docker-compose.yml`, `.github/` не создаются;
- `docs/architecture.md`, `CLAUDE.md`, `docs/dev-log.md` не изменяются;
- строка подключения к БД не попадает ни в `alembic.ini`, ни в логи.

## Критерий приёмки

- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src`
  проходят;
- на поднятой PostgreSQL 16 последовательность
  `uv run alembic upgrade head`, `uv run alembic downgrade base`,
  `uv run alembic upgrade head` проходит полностью, без ручного
  вмешательства между шагами;
- после `upgrade head` запрос `SELECT count(*) FROM currencies` возвращает 9;
- имена ограничений в базе соответствуют соглашению 4.1: запрос
  `SELECT conname FROM pg_constraint WHERE conrelid IN ('users'::regclass, 'currencies'::regclass)`
  даёт имена вида `pk_users`, `pk_currencies`, `uq_users_telegram_id`,
  `fk_users_base_currency`, `ck_currencies_*`. Фактический вывод привести в
  разделе результата;
- `grep -i 'sqlalchemy.url' alembic.ini` не показывает строки с реальным
  паролем или хостом;
- `uv run alembic check` после `upgrade head` не находит расхождений между
  метаданными и схемой.

## Результат исполнителя

**Сделано.** Написана инфраструктура БД для этапа 0 и первая миграция.

`src/finplan/infrastructure/db/base.py`: `Base(DeclarativeBase)` с
`MetaData(naming_convention=...)`, все пять шаблонов раздела 4.1 — `pk`,
`fk`, `uq`, `ck`, `ix` — дословно.

`src/finplan/infrastructure/db/engine.py`: `create_engine(database, *,
pool_size=None, max_overflow=None, echo=None)` принимает либо секцию
`DatabaseSettings` (тогда параметры пула по умолчанию читаются из неё —
`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_ECHO`), либо
готовую строку подключения (тогда действуют дефолты модуля, переопределяемые
именованными аргументами); окружение функция не читает сама.
`create_sessionmaker(engine)` — `async_sessionmaker` с
`expire_on_commit=False`.

ORM-модели `infrastructure/db/models/currencies.py` (`Currency`) и
`infrastructure/db/models/users.py` (`User`) — столбцы, типы и ограничения
по разделу 4.3 дословно: `char(3)` для кодов валют, `DateTime(timezone=True)`
(рендерится в `timestamptz`) для меток времени, `Uuid` (рендерится в нативный
`uuid` на PostgreSQL) для `id`, `CHECK (minor_unit BETWEEN 0 AND 4)`,
`UNIQUE` на `telegram_id`, `FOREIGN KEY users.base_currency → currencies.code`.
У `users.id` нет питоновского значения по умолчанию — только тип столбца.
`infrastructure/db/models/__init__.py` импортирует обе модели, чтобы
`Base.metadata` собиралась одним импортом пакета.

Корневой `alembic.ini`: `script_location = migrations`, строки подключения в
файле нет вообще (ни `sqlalchemy.url`, ни закомментированной — раздел 10.2),
`file_template` даёт имена файлов вида
`20260921_1730-fc2037cdf9d2_create_currencies_and_users.py` (дата, время,
ревизия, слаг).

`migrations/env.py` — async-вариант: строка подключения только из
`finplan.config.get_settings().database`, `target_metadata = Base.metadata`
после импорта `finplan.infrastructure.db.models` (регистрирует модели),
`compare_type=True` в online- и offline-режимах, `render_as_batch` не
задавался. Offline-режим (`alembic upgrade head --sql`) проверен вручную —
рендерит корректный DDL без подключения к БД. Добавлен также
`migrations/script.py.mako` (шаблон новой ревизии для `make revision`,
стандартный async-шаблон Alembic под Python 3.12).

Первая миграция `migrations/versions/20260921_1730-fc2037cdf9d2_create_currencies_and_users.py`:
создаёт `currencies`, затем `users` (порядок из-за FK), наполняет
`currencies` девятью строками (`RUB`, `USD`, `EUR`, `CNY`, `KZT`, `GEL`,
`TRY`, `AED`, `RSD`), у всех `minor_unit = 2`; символ проставлен только там,
где он общепринят и однозначен (`₽ $ € ¥ ₸ ₾ ₺`), для `AED` и `RSD` —
`NULL`, устойчивого символа у них нет. `downgrade` рабочий — удаляет `users`,
затем `currencies`.

Технически значимая находка при написании миграции: `CheckConstraint.name`
у SQLAlchemy всегда пропускается через `naming_convention` (в отличие от
PK/FK/UQ, где явное имя используется как есть) — а `alembic.op.create_table`
копирует `naming_convention` из `target_metadata` env.py в свою временную
`MetaData`. Если в миграции передать уже полное имя
`"ck_currencies_minor_unit_range"`, получится удвоение
`ck_currencies_ck_currencies_minor_unit_range` — воспроизведено и проверено
отдельным примером на голом SQLAlchemy без Alembic. В миграции используется
короткое имя `"minor_unit_range"`, как и в ORM-модели — так конвенция
добавляет префикс один раз и даёт `ck_currencies_minor_unit_range`.

`src/finplan/infrastructure/db/revision.py`: `check_revision(connection, *,
script_location=DEFAULT_SCRIPT_LOCATION)` — принимает `AsyncConnection` или
`AsyncSession`, сравнивает `get_head_revision()` (читает `head` из
`ScriptDirectory` файлов миграций на диске) с `get_database_revision()`
(читает `alembic_version.version_num`; `None`, если таблицы ещё нет —
`to_regclass` вместо try/except, чтобы не портить транзакцию соединения при
отсутствии таблицы). При расхождении поднимает `RevisionMismatchError` с
обеими ревизиями в сообщении; при совпадении возвращает `RevisionStatus`.
Вызов из точек входа (`api`/`bot`/`worker`) — предмет отдельной подзадачи,
здесь функция только написана и проверена вручную тремя сценариями (см.
«Проверка»).

**Проверка.**
- PostgreSQL 16 поднята командой `docker run -d --name finplan-pg -e
  POSTGRES_DB=finplan -e POSTGRES_USER=finplan -e POSTGRES_PASSWORD=finplan
  -p 5432:5432 postgres:16-alpine`; `.env` временно скопирован из
  `.env.example` (в нём `DATABASE_URL` уже указывает на `localhost:5432`
  под теми же учётными данными); после всех проверок контейнер остановлен и
  удалён (`docker rm -f finplan-pg`), `.env` удалён.
- `uv run ruff check` — `All checks passed!`.
- `uv run ruff format --check` — `58 files already formatted`.
- `uv run mypy src` — `Success: no issues found in 48 source files`.
- Последовательность `uv run alembic upgrade head` → `uv run alembic
  downgrade base` → `uv run alembic upgrade head` (прогонялась дважды подряд
  без ручного вмешательства между шагами) — все шаги успешны, лог
  `Running upgrade  -> fc2037cdf9d2, create currencies and users` /
  `Running downgrade fc2037cdf9d2 -> , create currencies and users`.
- `SELECT count(*) FROM currencies;` после `upgrade head` → `9`.
- `SELECT conname FROM pg_constraint WHERE conrelid IN ('users'::regclass,
  'currencies'::regclass) ORDER BY conname;` — фактический вывод:
  ```
  ck_currencies_minor_unit_range
  fk_users_base_currency
  pk_currencies
  pk_users
  uq_users_telegram_id
  ```
  (изначально до правки короткого имени `CheckConstraint` вывод содержал
  `ck_currencies_ck_currencies_minor_unit_range` — исправлено, см. «Сделано»,
  и перепроверено).
- `grep -i 'sqlalchemy.url' alembic.ini` — пустой вывод, код возврата 1
  (совпадений нет); строки `sqlalchemy.url` в файле нет вообще.
- `uv run alembic check` после `upgrade head` — `No new upgrade operations
  detected.`
- Ручная проверка `revision.py` вне критерия приёмки (тремя сценариями
  через реальное соединение с поднятой PostgreSQL): (1) БД на `head` —
  `check_revision` возвращает `RevisionStatus(database_revision='fc2037cdf9d2',
  head_revision='fc2037cdf9d2')`, не бросает исключение; (2) `alembic_version`
  испорчена (`UPDATE ... SET version_num = 'deadbeef0000'`) —
  `RevisionMismatchError: database revision is 'deadbeef0000', code head is
  'fc2037cdf9d2': run 'alembic upgrade head' before starting the app`; (3)
  после `alembic downgrade base` (таблицы `alembic_version` нет) —
  `RevisionMismatchError` с `database_revision=None`, `head_revision=
  'fc2037cdf9d2'`. После проверки состояние БД восстановлено обратно на
  `head`.
- `uv run alembic upgrade head --sql` (офлайн-режим, `.env` подставлен
  временно) — рендерит ожидаемый DDL `CREATE TABLE currencies (...)`,
  `CREATE TABLE users (...)` с теми же именами ограничений, без подключения
  к БД.

**Решения и отложенное.**
- `create_engine` в `engine.py` типизирована как принимающая
  `DatabaseSettings | str`, а не полный `Settings`: `Settings.database` —
  единственная секция, откуда фабрике engine нужны данные, передача всего
  `Settings` добавила бы ненужную связанность инфраструктурного модуля со
  всеми остальными секциями конфигурации (Telegram, JWT и т.д.).
- Для `id`, `timestamptz`-столбцов и `char(3)` выбраны переносимые типы
  SQLAlchemy 2.x — `sqlalchemy.Uuid()`, `sqlalchemy.DateTime(timezone=True)`,
  `sqlalchemy.CHAR(3)` — вместо `postgresql.UUID`/`postgresql.TIMESTAMP`:
  они компилируются в те же PostgreSQL-типы (проверено `CreateTable(...).
  compile(dialect=postgresql.dialect())` перед правкой моделей), но не
  привязывают модели к конкретному диалекту без необходимости.
- `migrations/versions/` — единственная миграция создана командой `uv run
  alembic revision -m "create currencies and users"` (чтобы получить
  реальный revision id и имя файла по `file_template`), тело `upgrade`/
  `downgrade` дописано вручную; `--autogenerate` не использовался, так как
  на момент миграции БД была пустой и autogenerate предложил бы то же
  самое, а порядок таблиц и заполнение `currencies` всё равно требуют
  ручной правки.
- `migrations/script.py.mako` добавлен, хотя в дереве раздела 2.1 явно не
  назван (в дереве под `migrations/` перечислены только `env.py` и
  `versions/`): без него не работает `make revision`/`alembic revision`,
  использованный для генерации самой этой миграции. Файл — стандартный
  шаблон Alembic (async), не архитектурное решение, а необходимая деталь
  работы самого Alembic внутри уже существующего каталога `migrations/`.
- Проверка идемпотентности констрейнтов и типов выполнена только против
  реальной PostgreSQL 16 в одноразовом контейнере, без testcontainers и без
  автоматизированного теста в `tests/integration/repositories/` — по заданию
  этой подзадачи проверка ручная, а `tests/` этой подзадачей не пишутся.

**Вопросы диспетчеру.**

Нет.
