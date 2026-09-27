# Use case записи этапа 1: регистрация, поиск пользователя, операция, сторно

- **Исполнитель:** developer
- **Слой:** application
- **Раздел архитектуры:** docs/architecture.md, разделы 2.2 (включая «Контракт портов и граница транзакции»), 3.3 (`User`, `Account`, `Transaction`, «Форма сторно»), 4.2, 6.1, 12.3
- **Заведена:** 2026-09-23

## Входные условия

Готово и не меняется в этой задаче:

- домен: `Money`, `Currency`, `Period`, сущности `User`, `Account`,
  `Category` с `build_default_categories`, `Transaction` с фабрикой `new` и
  методом `reverse`, ошибки `domain/common/errors.py`;
- порты: `application/ports/repositories.py` (`UserRepository`,
  `AccountRepository`, `CategoryRepository`, `TransactionRepository`,
  `LedgerQueries`, `DuplicateError`), `ports/uow.py` (`UnitOfWork`,
  `UnitOfWorkFactory`), `ports/clock.py` (`Clock`);
- DTO в `application/dto/` с методами `from_entity` у `UserDTO`,
  `AccountDTO`, `CategoryDTO`, `TransactionDTO` — перевод из домена в DTO
  делается только ими;
- ошибки сценариев: `application/errors.py` (`NotFoundError`,
  `InvalidCommandError`).

Прочитать до первой правки:

- `docs/architecture-brief.md` — карта и правила слоёв и денег;
- раздел 2.2 `docs/architecture.md` по номерам строк из карты, абзац
  «Контракт портов и граница транзакции» целиком;
- в разделе 3.3 — описание `Transaction` и абзац «Форма сторно»;
- сигнатуры `Transaction.new`, `Transaction.reverse`,
  `build_default_categories` и поля `Account` — кусками;
- DTO `dto/auth.py` и `dto/transactions.py`.

Параллельно с этой задачей другой исполнитель пишет use case чтения в
`use_cases/accounts/`, `use_cases/categories/` и `use_cases/reports/`. Эти
каталоги не трогать.

## Задание

Четыре use case. Каждый — отдельный модуль и класс с `async def __call__`,
который принимает DTO из `application/dto/` и возвращает DTO. Зависимости
принимаются в конструкторе: `UnitOfWorkFactory` и, где нужно время, `Clock`.
Транзакция открывается внутри `__call__` через
`async with self._uow_factory(user_id) as uow:` и фиксируется явным
`await uow.commit()`; сценарий только чтения `commit` не вызывает.
Идентификаторы новых сущностей — `uuid.uuid4()`. У класса докстрока на
русском, одна-две строки. Классы экспортируются из `__init__.py` своего
пакета.

### `use_cases/auth/find_user.py` — `FindUserByTelegramId`

`FindUserByTelegramIdQuery` → `UserDTO | None`. Фабрика вызывается с
`None`: `id` пользователя ещё неизвестен. Его вызывает `UserMiddleware`.

### `use_cases/auth/register_user.py` — `RegisterUser`

`RegisterUserCommand` → `RegisterUserResult`. Порядок:

1. Сгенерировать `new_id = uuid4()` и открыть `uow_factory(new_id)`.
   `uow.users.get_by_telegram_id` — если пользователь найден, перейти к
   шагу 4.
2. Создать `User` с базовой валютой и таймзоной из команды, первый
   `Account` с `opening_balance` в базовой валюте и `opened_at` — датой
   `clock.now()` в таймзоне пользователя (`zoneinfo.ZoneInfo`), и дерево
   категорий через `build_default_categories(user_id=new_id,
   id_factory=uuid4, ...)`. Сохранить через `users.add`, `accounts.add`,
   `categories.add_many`, затем `commit`. Вернуть `created=True`.
3. Если `users.add` или `commit` бросил `DuplicateError` — параллельный
   `/start` того же `telegram_id` успел раньше. Перейти к шагу 4.
4. Существующий пользователь: открыть новую транзакцию
   `uow_factory(existing.id)` (RLS видит данные только своего `user_id`),
   взять первый неархивный счёт из `accounts.list` и вернуть
   `created=False`. Если неархивных счетов нет — `NotFoundError`.

Поиска `Currency` по коду в домене нет: там только константы `RUB`,
`USD`, `EUR` из `domain/common/currency.py`, а конструктору нужен ещё
`minor_unit`. Поэтому код валюты из команды переводится в `Currency`
модульным словарём `{c.code: c for c in (RUB, USD, EUR)}` в
`register_user.py`. Неизвестный код — `InvalidCommandError`. Поиск по
коду в домен не выносить.

### `use_cases/transactions/record_transaction.py` — `RecordTransaction`

`RecordTransactionCommand` → `TransactionDTO`. Только `kind` `expense` и
`income`; иной `kind` — `InvalidCommandError` (переводы — этап 2).

1. `uow_factory(command.user_id)`. Загрузить пользователя
   (`users.get`), счёт (`accounts.get`) и категорию (`categories.get`, если
   `category_id` задан). Нет пользователя, счёта или категории, счёт или
   категория архивированы — `NotFoundError`.
2. Вид категории не совпадает с видом операции — `InvalidCommandError`.
   Валюта счёта не равна базовой валюте пользователя — тоже
   `InvalidCommandError`: курсов на этапе 1 нет.
3. `now = clock.now()`; `occurred_at = command.occurred_at or now`.
   `Transaction.new(..., status=posted, amount=Money(command.amount,
   currency_счёта), base_amount=command.amount, base_currency=валюта
   пользователя, base_rate=Decimal(1), created_at=now, now=now,
   external_key=command.external_key, source=command.source, ...)`.
4. `transactions.add`, `commit`. `DuplicateError` при повторе
   `external_key` пропускается наверх без обёртки: по разделу 12.3 бот
   отвечает на неё «Уже сохранено».

### `use_cases/transactions/undo_last.py` — `UndoLastTransaction`

`UndoLastCommand` → `UndoResultDTO | None`.

1. `uow_factory(command.user_id)`;
   `transactions.last_reversible(user_id, source)`. `None` — вернуть
   `None` без `commit`.
2. `original.reverse(reversal_id=uuid4(), created_at=clock.now())` —
   возвращает пару (исходная в `reversed`, сторнирующая запись).
3. `transactions.mark_reversed(user_id, original.id)`,
   `transactions.add(reversal)`, `commit`. Исходная операция другими
   способами не изменяется и не удаляется (раздел 4.2).
4. Вернуть `UndoResultDTO` из пары, возвращённой доменом.

## Границы

- изменяются и создаются только файлы в
  `src/finplan/application/use_cases/auth/` и
  `src/finplan/application/use_cases/transactions/`;
- `src/finplan/domain/`, `src/finplan/application/ports/`,
  `src/finplan/application/dto/`, `src/finplan/application/errors.py`,
  `docs/` не изменяются; если без их правки не обойтись — вопрос
  диспетчеру;
- новых зависимостей в `pyproject.toml` нет;
- тесты не пишутся: это подзадача 6, отдельный исполнитель `tester`;
- `float` в коде не встречается;
- `docs/dev-log.md` не трогать.

## Критерий приёмки

- существуют четыре модуля с классами `FindUserByTelegramId`,
  `RegisterUser`, `RecordTransaction`, `UndoLastTransaction`, и каждый
  импортируется из своего пакета;
- `grep -rn "float" src/finplan/application/use_cases` пуст;
- `make lint` зелёный (включая `ruff format --check`);
- `make test` зелёный, `tests/unit/test_layering.py` проходит;
- `git diff --stat` не выходит за два названных каталога.

## Результат исполнителя

**Сделано.** Реализованы четыре use case записи этапа 1.
`FindUserByTelegramId` (`use_cases/auth/find_user.py`) ищет пользователя по
`telegram_id` через `uow_factory(None)`, транзакцию не коммитит — сценарий
только чтения. `RegisterUser` (`use_cases/auth/register_user.py`) открывает
транзакцию `uow_factory(new_id)`, при отсутствии пользователя создаёт `User`,
первый `Account` (валюта и `opening_balance` — из команды, `opened_at` —
дата `clock.now()` в таймзоне пользователя через `zoneinfo.ZoneInfo`) и
дерево категорий через `build_default_categories`, сохраняет и коммитит;
код валюты переводится в `Currency` модульным словарём
`_CURRENCIES = {c.code: c for c in (RUB, USD, EUR)}`, неизвестный код —
`InvalidCommandError`. При `DuplicateError` от `users.add`/`commit`
(параллельный `/start`) и при исходно найденном пользователе сценарий
переоткрывает транзакцию `uow_factory(existing.id)`, берёт первый
неархивный счёт из `accounts.list` (репозиторий уже фильтрует архивные по
умолчанию) и возвращает `created=False`; отсутствие пользователя после гонки
или отсутствие неархивных счетов — `NotFoundError`. `RecordTransaction`
(`use_cases/transactions/record_transaction.py`) допускает только `kind`
`expense`/`income` (иначе `InvalidCommandError` до открытия транзакции),
проверяет существование и неархивность счёта и категории, совпадение вида
категории с видом операции и валюты счёта с базовой валютой пользователя
(иначе `InvalidCommandError`), строит `Transaction.new` с `status=posted`,
`base_rate=Decimal(1)` и снимком базовой валюты пользователя, вызывает
`transactions.add` и `commit`; `DuplicateError` по `external_key`
пробрасывается наверх без обёртки. `UndoLastTransaction`
(`use_cases/transactions/undo_last.py`) читает
`transactions.last_reversible`, при `None` возвращает `None` без `commit`,
иначе вызывает `Transaction.reverse`, помечает исходную операцию
`mark_reversed`, добавляет сторнирующую запись, коммитит и возвращает
`UndoResultDTO`, собранный из пары, которую вернул домен. Все четыре класса
экспортированы из `__init__.py` своих пакетов (`use_cases/auth`,
`use_cases/transactions`).

**Проверка.** `grep -rn "float" src/finplan/application/use_cases` — пусто.
`uv run ruff check` (весь репозиторий) — `All checks passed!`.
`uv run ruff format --check` (весь репозиторий) — `104 files already
formatted` (после автоформатирования `register_user.py` инструментом).
`uv run mypy src` — `Success: no issues found in 79 source files`.
`uv run pytest -q` — `108 passed in 7.48s`, включая отдельный прогон
`tests/unit/test_layering.py` — `3 passed`. `python3 docs/build-brief.py
--check` — документ и выжимка совпадают. `git diff --stat` затрагивает
только `use_cases/auth/__init__.py` и `use_cases/transactions/__init__.py`
(плюс новые файлы `find_user.py`, `register_user.py`,
`record_transaction.py`, `undo_last.py`) — оба каталога из границ задания;
изменения `use_cases/accounts/`, `use_cases/categories/`,
`use_cases/reports/`, видимые в общем `git diff --stat`, принадлежат
параллельному исполнителю и не затронуты этой работой.

**Решения и отложенное.** Спецификация шага 4 регистрации опирается на уже
известный объект `existing: User`, но в ветке гонки (`DuplicateError` при
исходно не найденном пользователе) такого объекта нет — решено сделать
дополнительный read-only запрос `uow.users.get_by_telegram_id` через
`uow_factory(None)` (тот же контракт «`None` — только для поиска по
`telegram_id»), чтобы получить `existing` и продолжить по общей ветке шага
4; если и повторный поиск возвращает `None` (гонка не подтвердилась),
это тоже `NotFoundError` — в задании этот подслучай отдельно не описан.
Тесты не писались — согласно границам, это подзадача 6 для `tester`.

**Вопросы диспетчеру.** Нет.
