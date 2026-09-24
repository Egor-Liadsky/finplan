# Интеграционные тесты репозиториев и Unit of Work против PostgreSQL

- **Исполнитель:** tester
- **Слой:** tests (`tests/integration/repositories/`), проверяется infrastructure
- **Раздел архитектуры:** docs/architecture.md, раздел 11.1 (пирамида, PostgreSQL в контейнере, откат через `SAVEPOINT`), 4.5 (роли `finplan_app` и `finplan_worker`, RLS по `app.user_id`), 4.3 (таблицы, столбец `transactions.occurred_on`), 3.3 (инвариант `occurred_on` в таймзоне пользователя), 2.2 (Unit of Work — одна транзакция на вызов use case)
- **Заведена:** 2026-09-24

## Входные условия

Первая из двух частей подзадачи 10 плана
`docs/tasks/2026-09-23-stage1-plan.md`. Вторая часть — запросы журнала и
параметризованная проверка изоляции — в файле
`docs/tasks/2026-09-24-ledger-queries-isolation-tests.md` и запускается
после этой: она использует фикстуры, которые появятся здесь.

Готово к запуску: репозитории, Unit of Work и RLS (подзадача 9a,
`docs/tasks/done/2026-09-24-repositories-uow.md`), запросы журнала (9b),
поле `Transaction.occurred_on` (9c). Интеграционных тестов на
репозитории пока нет. Исполнитель 9a проверял репозитории вручную
временным файлом и удалил его; сценарий такой проверки описан в разделе
«Результат исполнителя» файла задачи 9a.

До первой правки прочитать:

- `docs/architecture-brief.md`, разделы 11.1 и 11.4 (там дословные копии);
  раздел 4.5 — по номерам строк из карты брифа;
- `tests/conftest.py` целиком: фикстуры `postgres_container`,
  `migrated_database`, `app_database_url`, `db_session`, маркер
  `integration`;
- `src/finplan/infrastructure/db/uow.py`, `rls.py`, `engine.py`;
- `src/finplan/infrastructure/db/repositories/*.py` — публичные методы;
- `src/finplan/application/ports/` — протоколы, которым репозитории
  соответствуют (там описан ожидаемый контракт, в том числе
  `DuplicateError`).

## Задание

1. **Фикстуры.** Завести фикстуры для работы с репозиториями под ролью
   `finplan_app`: именно под ней действует RLS, а существующая
   `db_session` работает под владельцем схемы и политики обходит. Нужны
   сессия под `finplan_app` с откатом после теста и
   `SqlAlchemyUnitOfWorkFactory`, чьи экземпляры открывают сессии в той
   же откатываемой внешней транзакции. Рекомендуемый путь —
   `async_sessionmaker(bind=connection, join_transaction_mode="create_savepoint")`
   поверх соединения с открытой внешней транзакцией. Фикстуры, нужные и
   второй части подзадачи, положить в
   `tests/integration/repositories/conftest.py`.

   Подводный камень, который обязан быть учтён: `set_config('app.user_id',
   …, true)` действует до конца **внешней** транзакции, а не до конца
   `SAVEPOINT`. Если в одной внешней транзакции сначала работает
   пользователь A, а затем открывается Unit of Work пользователя B или
   Unit of Work без пользователя, значение A может остаться выставленным,
   и тест изоляции пройдёт по ошибке. Как это устранено — сбросом
   значения в фикстуре, отдельной внешней транзакцией на каждого
   пользователя или иначе, — описать в результате.

2. **Репозитории, по файлу тестов на каждый:** `users`, `accounts`,
   `categories`, `transactions` в `tests/integration/repositories/`.
   Для каждого: запись сущности и чтение её обратно через `get` и `list`
   с совпадением всех полей, включая `Money` с точностью `Decimal` по
   `minor_unit` валюты; `DuplicateError` на нарушение уникального ключа
   там, где порт его обещает. Для пользователей — поиск
   `get_by_telegram_id` через функцию `find_user_by_telegram_id` до
   выставления `app.user_id`. Для счетов и категорий — фильтр
   `include_archived`. Для операций — `mark_reversed` и
   `last_reversible` (по `created_at DESC`, только `posted`, без
   сторнирующих записей, по заданному `source`).

3. **`occurred_on`.** Операция с `occurred_at` 2026-09-23 22:30 UTC у
   пользователя с таймзоной `Europe/Moscow` сохраняется с
   `transactions.occurred_on = 2026-09-24`; проверить и значением
   столбца прямым SQL, и чтением сущности через репозиторий.

4. **Unit of Work.** `commit()` сохраняет, выход без `commit()`
   откатывает, повторный `commit()` в одном экземпляре даёт
   `RuntimeError`, исключение внутри блока `async with` откатывает
   изменения.

5. **Базовая изоляция.** Пользователь B через Unit of Work со своим
   `user_id` не видит счёт, категорию и операцию пользователя A ни через
   `get`, ни через `list`. Полный параметризованный перебор всех
   публичных методов из раздела 11.4 — во второй части подзадачи, здесь
   не нужен.

Все тесты помечаются `pytestmark = pytest.mark.integration`.

## Границы

- `src/` не изменяется: `git diff --stat -- src` пуст. Найденный дефект
  продуктового кода не чинить, а описать в результате с `file:line` и
  тестом, который его показывает; такой тест пометить
  `pytest.mark.xfail(strict=True, reason=...)` со ссылкой на дефект.
- `migrations/` не изменяется.
- `tests/conftest.py` меняется только если без этого не обойтись;
  существующие фикстуры не переименовываются и не меняют поведение —
  на них держится `tests/integration/test_migrations.py`.
- Новые зависимости в `pyproject.toml` не добавляются.
- Запросы журнала (`infrastructure/db/queries/ledger.py`) здесь не
  тестируются — это вторая часть.

## Критерий приёмки

- `uv run pytest tests/integration/repositories -q` зелёный при
  работающем Docker; число тестов названо в результате;
- `make test` зелёный целиком;
- `uv run ruff check` и `uv run ruff format --check` чистые;
- есть тест, в котором пользователь B не видит данных пользователя A;
- есть тест на `occurred_on = 2026-09-24` из пункта 3;
- в результате описано, как решён подводный камень с `app.user_id` из
  пункта 1;
- `git diff --stat -- src migrations` пуст.

## Результат исполнителя

**Сделано.** Добавлен пакет `tests/integration/repositories/` с фикстурами
и четырьмя файлами тестов (по одному на репозиторий) — 26 тестов, все
помечены `pytestmark = pytest.mark.integration`.

`tests/integration/repositories/conftest.py` даёт:
- `app_connection` — соединение под ролью `finplan_app` с открытой внешней
  транзакцией, которая откатывается в конце теста, и `uow_factory` —
  `SqlAlchemyUnitOfWorkFactory` поверх `async_sessionmaker(bind=app_connection,
  join_transaction_mode="create_savepoint")`, как рекомендовано в задании;
- `reset_app_user_id` — явный сброс `app.user_id` на `app_connection`;
- `make_user`/`make_account`/`make_category`/`make_transaction` — фикстуры-
  фабрики доменных сущностей с осмысленными значениями по умолчанию и
  возможностью переопределить любое поле через `**overrides`. Реализованы
  как фикстуры, а не функции модуля: `tests/` не пакет, `import
  tests....conftest` из отдельного файла падает `ModuleNotFoundError` под
  `--import-mode=prepend` — тот же приём, что у `alembic_runner` в
  `tests/conftest.py`.

Ключевое архитектурное решение фикстур, которое стоит увидеть до чтения
тестов: **все `UnitOfWork` внутри одного теста — и владельца данных, и
«соседа» из `TestTenantIsolation` — открываются через одну и ту же
`uow_factory`, то есть на одном соединении и одной внешней транзакции**, а
не на двух независимых. Первая версия фикстур давала владельцу и соседу
разные соединения; черновые изоляционные тесты на ней проходили, но это был
ложный проход: `commit()` `SqlAlchemyUnitOfWork` — это `RELEASE SAVEPOINT`
внутри внешней, никогда не коммитящейся транзакции теста, а не настоящий
`COMMIT` PostgreSQL, поэтому данные владельца физически не существуют для
другого соединения при `READ COMMITTED` — тест «сосед ничего не видит»
проходил бы даже при полностью сломанной или отсутствующей RLS-политике и
без явного `WHERE user_id = ...` в репозитории просто потому, что читать
было ещё нечего. Обнаружено на первом прогоне (`test_get_by_telegram_id_
before_user_known` с независимыми соединениями упал с `found is None`
вместо ожидаемого пользователя — это и вскрыло проблему), после чего все
фикстуры и тесты изоляции переведены на общую `uow_factory`.

**Подводный камень `app.user_id` (пункт 1) решён так.** `SET LOCAL`/
`set_config(..., true)` живёт до конца внешней транзакции соединения, а не
до конца `SAVEPOINT`. Раз все `UnitOfWork` теста делят одну внешнюю
транзакцию, после `commit()` пользователя A значение `app.user_id = A`
остаётся выставленным в ней. Для любого следующего `UnitOfWork` с
известным `user_id` (в том числе соседа B) это неопасно: `SqlAlchemyUnitOfWork.
__aenter__` сам выполняет `set_config('app.user_id', str(user_id), true)`
первым запросом своей новой `SAVEPOINT` и тем самым явно перекрывает всё
выставленное раньше в той же внешней транзакции — `uow_factory(user_b.id)`
после `uow_factory(user_a.id)` всегда корректно видит только B без
дополнительных мер. Опасен только `UnitOfWork` с `user_id=None` (поиск по
`telegram_id` до того, как пользователь известен): `__aenter__` в этом
случае `app.user_id` не трогает вовсе и наследует значение, оставшееся от
предыдущего пользователя. В тестах это единственный раз встречается в
`test_get_by_telegram_id_before_user_known`; сам метод всё равно идёт через
функцию `SECURITY DEFINER`, которая `app.user_id`/RLS не читает, поэтому
унаследованное значение не повлияло бы на результат и в этом конкретном
случае. Тем не менее решено явным сбросом в фикстуре (`reset_app_user_id`,
`SELECT set_config('app.user_id', '', true)`), вызванным в тесте до
открытия `uow_factory(None)`, — способ «сбросом значения в фикстуре» из
задания, не полагающийся на то, что конкретный метод оказался нечувствителен
к оставшемуся значению.

Четыре файла тестов:
- `test_users.py` — `TestUserRepository` (7 тестов: round trip `add`/`get`,
  `get` несуществующего, `DuplicateError` на повтор `telegram_id`,
  `get_by_telegram_id` до и после выставления `app.user_id`, `None` при
  отсутствии) и `TestUnitOfWork` (4 теста пункта 4: `commit()` сохраняет,
  выход без `commit()` откатывает, исключение внутри блока откатывает,
  повторный `commit()` → `RuntimeError`);
- `test_accounts.py` — round trip `add`/`get` с точностью `Decimal` до
  4 знаков (`numeric(20, 4)`, раздел 4.1) при `minor_unit` RUB = 2, `list`
  всех полей, `include_archived`, `DuplicateError` на регистронезависимое
  совпадение имени, `TestTenantIsolation` (сосед не видит счёт ни через
  `get`, ни через `list`);
- `test_categories.py` — round trip `add_many`/`get` с родителем и
  алиасами, `list` по `kind` и `include_archived`, `DuplicateError` на
  повтор `path`, `TestTenantIsolation`;
- `test_transactions.py` — round trip `add`/`get` с точностью `Decimal`,
  `DuplicateError` на повтор `external_key`, `occurred_on` пункта 3
  (`occurred_at` 2026-09-23 22:30 UTC + `Europe/Moscow` → `occurred_on =
  2026-09-24`, проверено и прямым SQL на `app_connection`, и через
  `uow.transactions.get`), `mark_reversed` меняет `status`, `last_reversible`
  — по `created_at DESC`, только `posted`, по заданному `source` (в т.ч.
  после `mark_reversed` предыдущей операции возвращает предыдущую по
  времени), `None` при отсутствии кандидата, `TestTenantIsolation` (через
  `get` и `last_reversible` — `list` у `TransactionRepository` нет).

**Проверка.**
- `uv run pytest tests/integration/repositories -q` — `26 passed`.
- `make test` (= `uv run pytest`) — `188 passed`, включая 26 новых из этой
  задачи; регрессий в остальных тестах не обнаружено.
- `uv run ruff check` — `All checks passed!`.
- `uv run ruff format --check` — `131 files already formatted`.
- `make lint` целиком (`build-brief.py --check`, `ruff check`, `ruff format
  --check`, `mypy src`) — зелёный, `mypy src` — `Success: no issues found in
  89 source files` (тесты `mypy` не проверяет по конфигурации проекта,
  `[[tool.mypy.overrides]] strict` действует только на `finplan.domain.*` и
  `finplan.application.*`; целевая команда задания `uv run mypy src` эту
  задачу не касается и не запускалась отдельно от `make lint`, так как
  `src/` не менялся).
- `git diff --stat -- src migrations` — пусто.

**Решения и отложенное.**
- Тесты изоляции (`TestTenantIsolation`) проверяют поведение репозитория
  (`get`/`list` с явным `WHERE user_id = ...`), а не изолированно саму
  RLS-политику — это уже дословно покрыто `tests/integration/
  test_migrations.py::TestRowLevelSecurityUnderAppRole` (подзадача 8b), где
  проверка идёт прямым SQL без репозитория. Здесь цель — раздел 11.4,
  «чтобы чужие данные не возвращались через публичные методы репозитория»,
  и оба защитных рубежа (явный фильтр и RLS) при этом действуют одновременно
  — тест не различает, какой из них сработал, и это оставлено осознанно:
  различение потребовало бы временно отключать один из рубежей, а `src/`
  менять нельзя.
- Порядок элементов `AccountRepository.list` (`ORDER BY sort_order,
  created_at` в реализации) не проверяется: `sort_order` — столбец ORM без
  соответствующего поля в доменной сущности `Account` (в отличие от
  `Category`, где `sort_order` есть), поэтому `test_list_round_trip_
  includes_all_fields` сравнивает результат как отображение `id → Account`,
  а не список — иначе тест был бы либо неустойчивым к точности `datetime.
  now(UTC)` двух последовательных вставок, либо проверял бы деталь
  инфраструктуры, которой нет в контракте порта.
- Полный параметризованный перебор всех публичных методов репозиториев для
  изоляции (раздел 11.4, вторая половина) сознательно не сделан здесь —
  это явно вторая часть подзадачи 10
  (`docs/tasks/2026-09-24-ledger-queries-isolation-tests.md`), которая
  переиспользует фикстуры этого файла, включая паттерн «общая
  `uow_factory`, а не отдельные соединения».
- Продуктовых дефектов в `src/` не найдено: `occurred_on` уже
  соответствует таймзоне пользователя (правка из коммита
  `2f95234 fix(transactions): record occurred_on in the user's timezone`,
  предшествующего этой задаче) — тест `test_occurred_on_uses_user_timezone`
  подтверждает это на реальной PostgreSQL, а не только на уровне домена.

**Вопросы диспетчеру.**
Нет.
