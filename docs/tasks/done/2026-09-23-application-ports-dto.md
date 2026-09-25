# Порты и DTO слоя application для этапа 1

- **Исполнитель:** developer
- **Слой:** application
- **Раздел архитектуры:** docs/architecture.md, разделы 2.1, 2.2 (включая «Контракт портов и граница транзакции»), 3.3, 4.2, 4.5, 8.5 (пункт 2 «Репозитории»)
- **Заведена:** 2026-09-23

## Входные условия

Доменное ядро этапа 1 готово и проверено ревью: `Money`, `Currency`,
`Period`, сущности `User`, `Account`, `Category`, `Transaction` с
перечислениями `AccountType`, `CategoryKind`, `TransactionKind`,
`TransactionStatus`, доменные ошибки в `domain/common/errors.py`. Каталоги
`src/finplan/application/dto/` и `src/finplan/application/ports/` существуют
и содержат только `__init__.py`.

Прочитать до первой правки:

- `docs/architecture-brief.md` — карта документа и правила слоёв и денег;
- раздел 2.2 `docs/architecture.md` целиком, особенно новый абзац «Контракт
  портов и граница транзакции»: он задаёт форму `UnitOfWork`, фабрики,
  `ledger`, `DuplicateError`, `Clock` и настройки DTO;
- пункт 2 раздела 8.5: ни один метод репозитория не принимает
  идентификатор объекта без `user_id`;
- сигнатуры сущностей в `src/finplan/domain/entities/*.py` — кусками, по
  полям классов, а не файлы целиком.

## Задание

Написать протоколы портов и DTO всех use case этапа 1. Реализаций портов и
самих use case в этой задаче нет: они — подзадачи 5a, 5b и 9a, 9b плана
`docs/tasks/2026-09-23-stage1-plan.md`.

Протоколы — `typing.Protocol`, методы асинхронные, кроме `Clock.now` и
`UnitOfWorkFactory.__call__`. Коллекции в результатах — `Sequence` или
`Mapping`, а не конкретные `list` и `dict`. У каждого протокола и метода —
докстрока на русском в одну-две строки: что возвращает и в каком случае
`None`.

### `application/ports/clock.py`

`Clock` с методом `now() -> datetime`, который возвращает момент с
таймзоной UTC.

### `application/ports/repositories.py`

- `DuplicateError(Exception)` — реализация репозитория бросает её при
  нарушении уникального ключа (`external_key` операции, имя счёта, `path`
  категории).
- `UserRepository`: `get(user_id)`, `get_by_telegram_id(telegram_id: int)`
  — оба возвращают `User | None`; `add(user) -> None`.
- `AccountRepository`: `get(user_id, account_id) -> Account | None`;
  `list(user_id, *, include_archived: bool = False) -> Sequence[Account]`;
  `add(account) -> None`.
- `CategoryRepository`: `get(user_id, category_id) -> Category | None`;
  `list(user_id, kind: CategoryKind, *, include_archived: bool = False) ->
  Sequence[Category]`; `add_many(categories: Sequence[Category]) -> None`.
- `TransactionRepository`: `get(user_id, transaction_id) -> Transaction |
  None`; `add(transaction) -> None`; `mark_reversed(user_id,
  transaction_id) -> None` — единственное изменение строки журнала,
  которое допускает раздел 4.2: перевод статуса `posted` в `reversed`;
  `last_reversible(user_id, source: str) -> Transaction | None` —
  последняя по `created_at` операция с данным `source` в статусе `posted`
  и с пустым `reverses_id`.
- `CategoryTotal` — `@dataclass(frozen=True, slots=True)` с полями
  `category_id: UUID`, `kind: TransactionKind`, `base_amount: Decimal`.
- `LedgerQueries`, протокол чтения агрегатов журнала:
  - `account_movements(user_id) -> Mapping[UUID, Decimal]` — сумма
    движений по каждому счёту в валюте счёта, без `opening_balance`: доход
    со знаком плюс, расход со знаком минус, перевод — минус по
    `account_id` и плюс по `counter_account_id`. Счёт без операций в
    словарь не попадает.
  - `totals_by_category(user_id, start: datetime, end: datetime) ->
    Sequence[CategoryTotal]` — суммы `base_amount` операций `expense` и
    `income` по категориям за полуинтервал `[start, end)` по
    `occurred_at`.
  - В докстроке протокола сказать, что учитываются только операции в
    статусе `posted`.

### `application/ports/uow.py`

- `UnitOfWork`: атрибуты `users`, `accounts`, `categories`,
  `transactions`, `ledger` с типами протоколов выше; `async __aenter__()
  -> Self`; `async __aexit__(exc_type, exc, tb) -> None`, который
  откатывает незакоммиченную транзакцию; `async commit() -> None`;
  `async rollback() -> None`.
- `UnitOfWorkFactory`: `__call__(user_id: UUID | None) -> UnitOfWork`. В
  докстроке — для чего `None` (раздел 2.2).

`fx_provider.py` и `notifier.py` из дерева 2.1 в этап 1 не входят и не
создаются.

### `application/dto/`

По файлу на группу use case: `base.py`, `auth.py`, `accounts.py`,
`categories.py`, `transactions.py`, `reports.py`. В `base.py` — базовая
модель `Dto(BaseModel)` с `model_config = ConfigDict(frozen=True,
strict=True, extra="forbid")`; все DTO наследуются от неё. Деньги —
`Decimal` плюс код валюты строкой `currency: str`; `Money` и `float` в DTO
не встречаются. Перечисления домена в полях DTO допустимы. Кортежи
вместо списков в полях-коллекциях, чтобы DTO оставались неизменяемыми.

- `auth.py`: `UserDTO` (`id`, `telegram_id`, `username`, `first_name`,
  `base_currency`, `timezone`, `locale`); `RegisterUserCommand`
  (`telegram_id`, `username`, `first_name`, `base_currency`, `timezone`,
  `account_name`, `account_type: AccountType`, `opening_balance: Decimal`)
  и результат `RegisterUserResult` (`user: UserDTO`, `account: AccountDTO`,
  `created: bool` — ложно, если пользователь с этим `telegram_id` уже был);
  `FindUserByTelegramIdQuery` (`telegram_id`) — результат use case
  `UserDTO | None`, отдельной модели не нужно.
- `accounts.py`: `AccountDTO` (`id`, `name`, `type: AccountType`,
  `currency`, `is_archived`); `ListAccountsQuery` (`user_id`) и
  `AccountListDTO` (`items: tuple[AccountDTO, ...]`); `GetBalancesQuery`
  (`user_id`), `AccountBalanceDTO` (`account: AccountDTO`, `balance:
  Decimal`) и `BalancesDTO` (`items`, `total: Decimal`, `currency` —
  базовая валюта пользователя).
- `categories.py`: `CategoryDTO` (`id`, `parent_id`, `kind: CategoryKind`,
  `name`, `path`, `depth`); `ListCategoriesQuery` (`user_id`, `kind`) и
  `CategoryListDTO` (`items`).
- `transactions.py`: `RecordTransactionCommand` (`user_id`, `kind:
  TransactionKind`, `amount: Decimal` с `Field(gt=0)`, `account_id`,
  `category_id`, `occurred_at: datetime | None` — `None` означает «сейчас
  по `Clock`», `comment: str | None`, `external_key: str | None`,
  `source: str`); `TransactionDTO` (`id`, `kind`, `status`, `amount`,
  `currency`, `account_id`, `category_id`, `occurred_at`, `comment`,
  `reverses_id`, `created_at`); `UndoLastCommand` (`user_id`, `source`) и
  `UndoResultDTO` (`original: TransactionDTO`, `reversal: TransactionDTO`)
  — результат use case `UndoResultDTO | None`, где `None` означает «нечего
  сторнировать».
- `reports.py`: `PeriodSummaryQuery` (`user_id`, `scope:
  Literal["day", "month"]`); `CategoryTotalDTO` (`category_id`, `name`,
  `total: Decimal`) — суммы свёрнуты до корневых категорий, то есть
  категорий с `depth = 0`; `PeriodSummaryDTO` (`start: date`, `end: date`
  — полуинтервал в таймзоне пользователя, `currency`, `expense_total`,
  `income_total`, `expenses: tuple[CategoryTotalDTO, ...]`, `incomes:
  tuple[CategoryTotalDTO, ...]`).

Если поле из этого списка противоречит полям сущности или разделу 3.3, не
подгонять: записать вопрос в «Вопросы диспетчеру» и сделать остальное.

## Границы

- изменяются и создаются только файлы в `src/finplan/application/ports/` и
  `src/finplan/application/dto/`;
- `src/finplan/domain/`, `src/finplan/application/use_cases/`, `tests/`,
  `docs/` не изменяются, кроме раздела «Результат исполнителя» этого файла;
- новые зависимости в `pyproject.toml` не добавляются: pydantic уже есть;
- тесты не пишутся: их пишет `tester` в подзадаче 6.

## Критерий приёмки

- существуют `ports/clock.py`, `ports/repositories.py`, `ports/uow.py` и
  шесть файлов DTO из списка выше с названными классами и полями;
- файлы импортируют только стандартную библиотеку, `pydantic` и
  `finplan.domain`; `grep -rn "float" src/finplan/application` пуст;
- `uv run python -c` с попыткой создать `RecordTransactionCommand` с
  `amount=1.5` падает с `ValidationError`, а с `amount=Decimal("1.5")`
  проходит — команду и её вывод привести в результате;
- `make lint` и `make test` зелёные, включая `tests/unit/test_layering.py`
  и `mypy`;
- `git diff --stat` не выходит за `src/finplan/application/ports/`,
  `src/finplan/application/dto/` и этот файл задачи.

## Результат исполнителя

**Сделано.** Написаны протоколы портов этапа 1 и DTO всех его use case, без
реализаций и без самих use case. `ports/clock.py` — `Clock.now()`
(единственный синхронный метод портов, наравне с
`UnitOfWorkFactory.__call__`). `ports/repositories.py` — `DuplicateError`,
`UserRepository`, `AccountRepository`, `CategoryRepository`,
`TransactionRepository` (включая `mark_reversed` и `last_reversible`),
`CategoryTotal` (`@dataclass(frozen=True, slots=True)`) и `LedgerQueries`
(`account_movements`, `totals_by_category`) — у каждого метода докстрока с
описанием случая `None`. `ports/uow.py` — `UnitOfWork` с атрибутами
`users`/`accounts`/`categories`/`transactions`/`ledger` и
`__aenter__`/`__aexit__`/`commit`/`rollback`, и `UnitOfWorkFactory.__call__(user_id:
UUID | None)`. Шесть файлов DTO (`base.py`, `auth.py`, `accounts.py`,
`categories.py`, `transactions.py`, `reports.py`) с классами из задания;
все наследуются от `Dto(BaseModel)` с `frozen=True, strict=True,
extra="forbid"`; деньги — `Decimal` плюс `currency: str`; коллекции —
`tuple[...]`, а не `list`; перечисления домена (`AccountType`,
`CategoryKind`, `TransactionKind`, `TransactionStatus`) используются в
полях DTO как есть. `RecordTransactionCommand.amount` — `Decimal =
Field(gt=0)`. Расхождений между списком полей задания и сущностями домена
не обнаружено — подгонки не потребовалось.

**Проверка.**

- `uv run ruff check src/finplan/application` — `All checks passed!`.
- `uv run mypy src` — `Success: no issues found in 70 source files`.
- `uv run pytest -q` — `108 passed in 7.23s`, включая
  `tests/unit/test_layering.py` (`3 passed`).
- `grep -rn "float" src/finplan/application` — пустой вывод (после правки
  докстроки в `base.py`, где слово `float` изначально встречалось только в
  тексте пояснения).
- `uv run python -c` с `RecordTransactionCommand(..., amount=1.5, ...)`
  падает:

  ```
  pydantic_core._pydantic_core.ValidationError: 1 validation error for RecordTransactionCommand
  amount
    Input should be an instance of Decimal [type=is_instance_of, input_value=1.5, input_type=float]
  ```

  С `amount=Decimal("1.5")` тот же вызов проходит: `cmd.amount ==
  Decimal("1.5")`.
- `git status --porcelain` подтверждает: все новые файлы — только в
  `src/finplan/application/ports/`, `src/finplan/application/dto/` и сам
  файл задачи (плюс `.claude/skills/jev-skill-suggestion/` и модификации
  `docs/architecture*.md`, `docs/tasks/2026-09-23-stage1-plan.md` — эти
  правки были в рабочем дереве уже на старте задачи, не мои).

**Решения и отложенное.** `RegisterUserResult` и `AccountBalanceDTO`
вкладывают `AccountDTO` целиком, а не только `id`/`name` — так задание
описывает поля буквально («`account: AccountDTO`»), и это ближе к тому, что
понадобится entrypoints для форматирования ответа без второго похода в
репозиторий. `RecordTransactionCommand` не включает
`counter_account_id`/`transfer_group_id` — в задании их нет, а `transfer` в
разделе задания на этап 1 не упомянут явно как часть DTO; если use case 9a/9b
понадобится перевод, это отдельное расширение DTO, не входящее в эту
задачу. Докстроки методов протоколов ограничены одной-двумя строками, где
это укладывалось по смыслу; там, где нужно было сослаться и на форму
результата, и на трактовку `None` (`last_reversible`,
`account_movements`), докстрока вышла на три строки — короче не потеряв
точности не получалось.

**Вопросы диспетчеру.** Нет.
