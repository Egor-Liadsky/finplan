# Запросы остатков и сумм по категориям

- **Исполнитель:** developer
- **Слой:** infrastructure
- **Раздел архитектуры:** docs/architecture.md, раздел 2.2 (абзац «Контракт портов и граница транзакции»), 3.1, 3.3 (сущность `Transaction`), 4.1, 4.2, 4.3 (таблицы `accounts`, `transactions`), 4.5
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 9b плана `docs/tasks/2026-09-23-stage1-plan.md`. Параллельно
с ней идёт подзадача 9a (`docs/tasks/2026-09-24-repositories-uow.md`):
репозитории, `uow.py` и `rls.py`. Эта задача их не читает и не
импортирует. Unit of Work из 9a получает реализацию `LedgerQueries`
через параметр `ledger_factory: Callable[[AsyncSession], LedgerQueries]`,
поэтому класс этой задачи обязан создаваться из одной `AsyncSession`.

Уже готово:

- протокол `LedgerQueries` и dataclass `CategoryTotal` в
  `src/finplan/application/ports/repositories.py`;
- ORM-модели в `src/finplan/infrastructure/db/models/`, в том числе
  `transactions.py` со столбцами `kind`, `status`, `amount`, `currency`,
  `account_id`, `counter_account_id`, `category_id`, `occurred_at`,
  `base_amount`, `transfer_group_id`;
- пустой пакет `src/finplan/infrastructure/db/queries/__init__.py`.

До первой правки прочитать:

- `docs/architecture-brief.md`;
- `docs/architecture.md` через `Read` с `offset` и `limit` по карте из
  выжимки: 2.2, 3.1, 4.1, 4.2; из 3.3 — сущность `Transaction`; из 4.3 —
  таблицы `accounts` и `transactions`, особенно правила хранения
  переводов;
- `src/finplan/application/ports/repositories.py`, класс `LedgerQueries`
  и `CategoryTotal`;
- `src/finplan/infrastructure/db/models/transactions.py` и `accounts.py`.

## Задание

1. **`src/finplan/infrastructure/db/queries/ledger.py`.** Класс
   `SqlAlchemyLedgerQueries(session: AsyncSession)`, реализующий протокол
   `LedgerQueries`. Имя модуля и класса зафиксированы: по ним
   `container.py` подключит класс к Unit of Work.

2. **`account_movements(user_id)`.** Один агрегирующий SQL-запрос, а не
   загрузка операций в Python. Семантика — по docstring порта: только
   `status = 'posted'`; доход плюс, расход минус, перевод минус по
   `account_id` и плюс по `counter_account_id`; сумма в валюте счёта,
   без `opening_balance`; счёт без операций в словарь не попадает.
   Как в 4.3 хранится перевод между счетами в разных валютах — одной
   строкой или парой строк с общим `transfer_group_id`, — прочитать в
   документе и считать по нему. Если документ этого не определяет или
   docstring порта с ним расходится, это вопрос диспетчеру: сделать
   `totals_by_category`, записать вопрос и остановиться.

3. **`totals_by_category(user_id, start, end)`.** Суммы `base_amount`
   операций `expense` и `income` со `status = 'posted'` по
   `category_id` и `kind` за полуинтервал `occurred_at >= start AND
   occurred_at < end`. Операции без категории в результат не попадают.

4. **Общие правила.**
   - каждый запрос фильтрует по `user_id` явно, даже при включённом RLS
     (4.5, ADR-008);
   - суммы возвращаются как `Decimal` из `Numeric`, без `float` и без
     округления в SQL (3.1). Отсутствие операций — пустой результат, а
     не ноль;
   - значения `kind` и `status` сравниваются с константами, взятыми из
     доменных перечислений, а не строковыми литералами, если модель
     хранит их значения.

5. **Проверка типов.** Под `if TYPE_CHECKING:` строка, которая заставляет
   `mypy` сверить класс с протоколом, например
   `_check: type[LedgerQueries] = SqlAlchemyLedgerQueries`.

## Границы

- `src/finplan/domain/` и `src/finplan/application/` не изменяются.
  Если порт не реализуется без правки — вопрос диспетчеру.
- Не создаются и не правятся `infrastructure/db/repositories/`,
  `infrastructure/db/uow.py`, `infrastructure/db/rls.py` — это 9a.
- Модели и миграции не изменяются; индексы, если нужны, — вопрос
  диспетчеру.
- `docs/architecture.md` не правится.
- `src/finplan/container.py` и `entrypoints/` не изменяются.
- Интеграционные тесты не пишутся — это подзадача 10. Допустима одна
  ручная проверка против PostgreSQL из testcontainers, результат
  называется в отчёте.
- `.env` не правится. Коммиты не делаются.

## Критерий приёмки

- существует `src/finplan/infrastructure/db/queries/ledger.py` с классом
  `SqlAlchemyLedgerQueries`, конструктор принимает одну `AsyncSession`;
- `uv run mypy src` зелёный, и проверка из пункта 5 на месте;
- `grep -n "float" src/finplan/infrastructure/db/queries/ledger.py` пуст;
- `make test` и `make lint` зелёные. Если `make lint` падает только на
  незаконченных файлах параллельной 9a, это называется в отчёте с
  решающей строкой вывода, а чужие файлы не правятся;
- `git diff --stat -- src/finplan/domain src/finplan/application` пуст.

## Результат исполнителя

**Сделано.** Создан `src/finplan/infrastructure/db/queries/ledger.py` с
классом `SqlAlchemyLedgerQueries(session: AsyncSession)`. `totals_by_category`
реализован одним агрегирующим SQL-запросом (`SELECT category_id, kind,
sum(base_amount) ... GROUP BY category_id, kind`) по модели
`infrastructure/db/models/transactions.Transaction`: фильтр по `user_id`
явно (независимо от RLS), `status = posted` и `kind IN (income, expense)` —
через значения `TransactionStatus`/`TransactionKind`, а не строковые
литералы, `category_id IS NOT NULL`, `occurred_at` в `[start, end)`. Суммы
приходят из `NUMERIC` как `Decimal` без округления в SQL; категория без
операций в результат не попадает (пустой список — не список нулей).

`account_movements` реализован по решению диспетчера (см. «Вопросы
диспетчеру» — вопрос закрыт): один агрегирующий запрос `UNION ALL` двух
подзапросов, сгруппированный по счёту. Первый подзапрос даёт вклад по
`account_id` — `+amount` для `income`, `-amount` для `expense` и
`transfer`; второй — вклад по `counter_account_id` — `+amount` только для
`transfer`. Оба фильтруют `user_id` явно и `status = posted`.
`transfer_group_id` в запросе не участвует: на этапе 1 переводов нет и
поля `transfer_group_id` у домена `Transaction` тоже нет, кросс-валютная
пара из раздела 3.3 остаётся вопросом этапа 2. Метод структурно и
функционально реализует протокол `LedgerQueries`; проверка типов из
пункта 5 задания — `if TYPE_CHECKING: _check: type[LedgerQueries] =
SqlAlchemyLedgerQueries` — на месте в конце файла.

**Проверка.**

- `uv run mypy src` (после решения диспетчера) — падает на трёх ошибках, но
  все они в файлах параллельной подзадачи 9a, не в `ledger.py`: решающая
  строка вывода —
  `src/finplan/infrastructure/db/uow.py:136: error: Incompatible types in
  assignment (expression has type "type[SqlAlchemyUnitOfWork]", variable
  has type "type[UnitOfWork]")  [assignment]`. Точечный прогон
  `uv run mypy src/finplan/infrastructure/db/queries/ledger.py` —
  `Success: no issues found in 1 source file`.
- `uv run ruff check src/finplan/infrastructure/db/queries/ledger.py` и
  `uv run ruff format --check` того же файла — зелёные.
- `make lint` целиком падает — тоже на файле 9a, не на моём: решающая
  строка — `unformatted: File would be reformatted` в
  `src/finplan/infrastructure/db/repositories/transactions.py:140`,
  команда завершается `make: *** [lint] Error 1`. Файлы 9a не правились.
- `grep -n "float" src/finplan/infrastructure/db/queries/ledger.py` — пусто.
- `make test` — зелёный, `158 passed`.
- `git diff --stat -- src/finplan/domain src/finplan/application` — пусто
  (слои не тронуты).
- Ручная проверка против реальной PostgreSQL 16 из `testcontainers`
  (дважды, скрипты в scratchpad, не сохранены в репозитории и не
  коммитились):
  - `totals_by_category`: пользователь, счёт, две категории, пять операций
    (две `expense` по 100.00 и 50.50, одна `income` 1000.00 в периоде,
    одна `expense` 999.00 со `status = reversed`, одна `expense` 777.00
    другого `user_id`). Результат ровно
    `{(cat_expense, expense): 150.50, (cat_income, income): 1000.00}` —
    сторно и чужая операция не попали, суммы — `Decimal`.
  - `account_movements` (после реализации по решению диспетчера): счета
    A, B, C одного пользователя; на A — `income` 500.00 и `expense`
    200.00 (`posted`), перевод A→B на 100.00 (`kind=transfer,
    account_id=A, counter_account_id=B`), и ещё `expense` 999.00 на A со
    `status=reversed`. Результат ровно
    `{A: Decimal("200.0000"), B: Decimal("100.0000")}`, счёт C без
    операций в словаре отсутствует, сторно не учтено.

**Решения и отложенное.**

- `account_movements` реализован ровно по инструкции диспетчера и
  докstring порта: `income` — плюс по `account_id`, `expense` — минус по
  `account_id`, `transfer` — минус по `account_id` и плюс по
  `counter_account_id`; только `status = posted`; `transfer_group_id` не
  учитывается. Кросс-валютная пара строк `transfer_group_id` из раздела
  3.3 — вопрос этапа 2, зафиксирован диспетчером в `docs/architecture.md`
  (раздел 3.3), здесь не переоткрывается.
- Индексы под новые запросы не добавлялись (модели/миграции задача не
  трогает). `ix_transactions_account_id_occurred_at` из 4.3 покрывает
  `account_id`, но не `counter_account_id`; `ix_transactions_user_id_occurred_at`
  покрывает `user_id`. Если план `account_movements` на реальных объёмах
  окажется медленным из-за подзапроса по `counter_account_id` без индекса
  — это отдельный вопрос, не решённый здесь.
- `make lint`/`uv run mypy src` в целом по репозиторию красные из-за
  незаконченных файлов параллельной подзадачи 9a (`uow.py`,
  `repositories/transactions.py`) — это не относится к этой задаче и не
  исправлялось (граница «чужие файлы не правятся»).

**Вопросы диспетчеру.**

Вопрос про `account_movements` и кросс-валютную пару `transfer_group_id`
закрыт решением диспетчера: на этапе 1 одна валюта и переводов нет вовсе,
поле `transfer_group_id` у домена `Transaction` отсутствует, поэтому
кросс-валютная пара строк из раздела 3.3 создана быть не может. Метод
реализован ровно по докstring порта и формуле раздела 5.7 (`income` плюс,
`expense` и `transfer` минус по `account_id`, `transfer` дополнительно
плюс по `counter_account_id`, только `status = posted`), `transfer_group_id`
в запросе не участвует. Пробел про представление кросс-валютной пары
диспетчер зафиксировал в `docs/architecture.md`, раздел 3.3, как решаемый
на этапе 2; в `ledger.py` рядом с запросом об этом же — однострочный
комментарий. Открытых вопросов по этой задаче больше нет.
