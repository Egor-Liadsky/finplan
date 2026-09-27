# Use case чтения этапа 1: счета, остатки, категории, сводка за период

- **Исполнитель:** developer
- **Слой:** application
- **Раздел архитектуры:** docs/architecture.md, разделы 2.2 (включая «Контракт портов и граница транзакции»), 3.1, 3.3 (`Account`, `Category`), 4.2, 6.1 (`/balance`, `/today`, `/month`)
- **Заведена:** 2026-09-23

## Входные условия

Готово и не меняется в этой задаче:

- домен: `Money`, `Currency`, `Period` с `for_day` и `for_month`,
  сущности `User`, `Account`, `Category`, ошибки
  `domain/common/errors.py`;
- порты: `application/ports/repositories.py` (`UserRepository`,
  `AccountRepository`, `CategoryRepository`, `LedgerQueries` с
  `account_movements` и `totals_by_category`, запись `CategoryTotal`),
  `ports/uow.py` (`UnitOfWork`, `UnitOfWorkFactory`), `ports/clock.py`
  (`Clock`);
- DTO в `application/dto/` с методами `from_entity` у `AccountDTO` и
  `CategoryDTO` — перевод из домена в DTO делается только ими;
- ошибки сценариев: `application/errors.py` (`NotFoundError`).

Прочитать до первой правки:

- `docs/architecture-brief.md` — карта и правила слоёв, денег и периодов;
- раздел 2.2 `docs/architecture.md` по номерам строк из карты, абзац
  «Контракт портов и граница транзакции» целиком;
- раздел 3.1 — правила `Money` и округления;
- `LedgerQueries` в `ports/repositories.py` и DTO `dto/accounts.py`,
  `dto/categories.py`, `dto/reports.py`;
- `domain/common/period.py` — кусками.

Параллельно с этой задачей другой исполнитель пишет use case записи в
`use_cases/auth/` и `use_cases/transactions/`. Эти каталоги не трогать.

## Задание

Четыре use case. Каждый — отдельный модуль и класс с `async def __call__`,
который принимает DTO из `application/dto/` и возвращает DTO. Зависимости
принимаются в конструкторе: `UnitOfWorkFactory` и, где нужно время, `Clock`.
Транзакция открывается через
`async with self._uow_factory(query.user_id) as uow:`; все сценарии здесь
только читают, `commit` не вызывается. Всё чтение одного вызова идёт в
одной транзакции. У класса докстрока на русском, одна-две строки. Классы
экспортируются из `__init__.py` своего пакета.

### `use_cases/accounts/list_accounts.py` — `ListAccounts`

`ListAccountsQuery` → `AccountListDTO`: неархивные счета пользователя в
порядке, в котором их вернул `accounts.list`. Для клавиатуры выбора счёта в
диалогах `/expense` и `/income`.

### `use_cases/categories/list_categories.py` — `ListCategories`

`ListCategoriesQuery` → `CategoryListDTO`: неархивные категории заданного
вида, в порядке репозитория. Для клавиатуры выбора категории.

### `use_cases/accounts/get_balances.py` — `GetBalances`

`GetBalancesQuery` → `BalancesDTO` для `/balance`.

1. `users.get` — нет пользователя, значит `NotFoundError`.
2. Неархивные счета из `accounts.list` и движения из
   `ledger.account_movements`. Остаток счёта — `opening_balance` плюс
   движение по счёту; счёта нет в словаре — движение ноль. Считать через
   `Money` в валюте счёта, в DTO класть `.amount`.
3. `total` — сумма остатков счетов с `include_in_networth`, через `Money`
   в базовой валюте пользователя; `currency` — код базовой валюты. Курсов
   на этапе 1 нет: счёт в другой валюте даст `CurrencyMismatchError` из
   домена, и её не перехватывать.

### `use_cases/reports/period_summary.py` — `GetPeriodSummary`

`PeriodSummaryQuery` → `PeriodSummaryDTO` для `/today` и `/month`.

1. `users.get` — нет пользователя, значит `NotFoundError`.
2. Сегодняшняя дата в таймзоне пользователя:
   `clock.now().astimezone(ZoneInfo(user.timezone)).date()`. `scope="day"`
   — `Period.for_day(today)`, `scope="month"` — `Period.for_month` текущего
   месяца. Период — полуинтервал `[start, end)`.
3. Границы запроса к журналу — полночь `period.start` и полночь
   `period.end` в таймзоне пользователя, переведённые в UTC;
   `ledger.totals_by_category(user_id, start, end)`.
4. Свернуть суммы до корневых категорий: загрузить категории обоих видов
   с `include_archived=True` (архивная категория всё равно попадает в
   отчёт), пройти по `parent_id` до корня, сложить суммы корня. Итоги
   `expense_total` и `income_total` — суммы по видам. Суммы в
   `CategoryTotal` положительные: сумма операции в домене всегда больше
   нуля.
5. Списки `expenses` и `incomes` отсортировать по убыванию суммы, при
   равенстве — по имени. В `PeriodSummaryDTO` `start` и `end` — даты
   периода, `currency` — код базовой валюты. Категория из `CategoryTotal`,
   которой нет среди загруженных, — `NotFoundError`.

## Границы

- изменяются и создаются только файлы в
  `src/finplan/application/use_cases/accounts/`,
  `src/finplan/application/use_cases/categories/` и
  `src/finplan/application/use_cases/reports/`;
- `src/finplan/domain/`, `src/finplan/application/ports/`,
  `src/finplan/application/dto/`, `src/finplan/application/errors.py`,
  `docs/` не изменяются; если без их правки не обойтись — вопрос
  диспетчеру;
- новых зависимостей в `pyproject.toml` нет;
- тесты не пишутся: это подзадача 6, отдельный исполнитель `tester`;
- `float` в коде не встречается;
- `docs/dev-log.md` не трогать.

## Критерий приёмки

- существуют четыре модуля с классами `ListAccounts`, `ListCategories`,
  `GetBalances`, `GetPeriodSummary`, и каждый импортируется из своего
  пакета;
- `grep -rn "float" src/finplan/application/use_cases` пуст;
- `make lint` зелёный (включая `ruff format --check`);
- `make test` зелёный, `tests/unit/test_layering.py` проходит;
- `git diff --stat` не выходит за три названных каталога.

## Результат исполнителя

**Сделано.** Реализованы четыре use case чтения этапа 1, каждый — отдельный
модуль с классом `async def __call__`, принимающим `UnitOfWorkFactory` (и
`Clock` для отчёта) в конструкторе и открывающим одну транзакцию на весь
вызов без `commit`. `ListAccounts` и `ListCategories` — тонкие обёртки над
`accounts.list`/`categories.list` в доменном порядке, без проверки
существования пользователя (в задании для них она не требуется). `GetBalances`
проверяет пользователя через `users.get`, считает остаток каждого неархивного
счёта как `opening_balance + Money(движение, валюта счёта)` (счёт без
движений — ноль), и сумму `total` по счетам с `include_in_networth` в базовой
валюте пользователя через сложение `Money`; смешение валют не перехватывается
и всплывает как `CurrencyMismatchError` домена, как и написано в задании.
`GetPeriodSummary` считает "сегодня" в таймзоне пользователя через
`clock.now().astimezone(ZoneInfo(...))`, строит `Period.for_day`/`for_month`,
переводит границы периода в UTC через `datetime.combine(..., tzinfo=...)`,
читает `ledger.totals_by_category`, затем сворачивает суммы до корневых
категорий, поднимаясь по `parent_id` по обеим загруженным (`include_archived
=True`) иерархиям видов; категория из `CategoryTotal`, отсутствующая среди
загруженных, даёт `NotFoundError`. Списки `expenses`/`incomes` отсортированы
по убыванию суммы, при равенстве — по имени. Классы экспортированы из
`__init__.py` своих пакетов (`accounts`, `categories`, `reports`).

**Проверка.** `uv run ruff check src/finplan/application/use_cases/accounts
src/finplan/application/use_cases/categories
src/finplan/application/use_cases/reports` — `All checks passed!`.
`uv run ruff format --check` по тем же трём каталогам — `7 files already
formatted`. `uv run mypy src` (весь проект) — `Success: no issues found in 75
source files`. `grep -rn "float" src/finplan/application/use_cases` — пусто.
`uv run pytest -q` — `108 passed in 7.35s`, включая `tests/unit/test_layering.py`.
Полный `uv run ruff check` и `python3 docs/build-brief.py --check` (части
`make lint`) тоже зелёные. Полный `uv run ruff format --check` (часть
`make lint`) падает на одном файле параллельного исполнителя:
`unformatted: File would be reformatted --> src/finplan/application/use_cases/
auth/register_user.py:87:37` — это не файл этой задачи, не правился по
инструкции. `git diff --stat` по трём названным каталогам — только
`accounts/__init__.py`, `categories/__init__.py`, `reports/__init__.py`
изменены, новые файлы — только внутри тех же трёх каталогов; файлы
`auth/`, `transactions/` параллельного исполнителя не тронуты.

**Решения и отложенное.** Для `ListAccounts`/`GetBalances` порядок счетов —
порядок `accounts.list` без дополнительной сортировки (в задании сортировка
для остатков не требуется, только для отчёта по категориям). Сортировка
корневых категорий отчёта реализована ключом `(-item.total, item.name)` —
`Decimal` допускает унарный минус, доп. компаратор не понадобился.
Вспомогательная функция `_sorted_totals` и алиас типа `_RootTotal` в
`period_summary.py` — приватные, только для читаемости модуля, в API use case
не участвуют.

**Вопросы диспетчеру.** Пусто.
