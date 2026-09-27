# Репозитории, Unit of Work и установка app.user_id

- **Исполнитель:** developer
- **Слой:** infrastructure
- **Раздел архитектуры:** docs/architecture.md, раздел 2.2 (абзац «Контракт портов и граница транзакции»), 4.1, 4.2, 4.3 (таблицы `users`, `accounts`, `categories`, `transactions`), 4.5 целиком; 8.5, пункт 2
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 9a плана `docs/tasks/2026-09-23-stage1-plan.md`. Параллельно
с ней идёт подзадача 9b (`docs/tasks/2026-09-24-ledger-queries.md`): она
пишет реализацию `LedgerQueries` в `src/finplan/infrastructure/db/queries/`.
Файлы 9b эта задача не читает и не импортирует — см. пункт 3 задания.

Уже готово:

- порты `src/finplan/application/ports/repositories.py` и
  `src/finplan/application/ports/uow.py`: протоколы `UserRepository`,
  `AccountRepository`, `CategoryRepository`, `TransactionRepository`,
  `LedgerQueries`, `UnitOfWork`, `UnitOfWorkFactory` и исключение
  `DuplicateError`;
- доменные сущности в `src/finplan/domain/entities/`;
- ORM-модели в `src/finplan/infrastructure/db/models/` и миграции с
  триггером неизменяемости журнала, ролями и политиками RLS;
- функция `find_user_by_telegram_id(bigint) RETURNS SETOF users` с
  `SECURITY DEFINER`, доступная роли `finplan_app`;
- `src/finplan/infrastructure/db/engine.py` с фабриками engine и
  sessionmaker;
- фикстуры `tests/conftest.py`: `migrated_database` (URL владельца),
  `app_database_url` (URL под `finplan_app`), `db_session`.

До первой правки прочитать:

- `docs/architecture-brief.md`;
- `docs/architecture.md` через `Read` с `offset` и `limit` по карте из
  выжимки: 2.2, 4.1, 4.5 целиком; из 4.3 — только таблицы `users`,
  `accounts`, `categories`, `transactions`;
- оба файла портов целиком;
- `src/finplan/domain/entities/*.py` — только конструкторы и поля;
- `src/finplan/infrastructure/db/models/*.py`;
- `tests/conftest.py`, строки 200–330.

## Задание

1. **`src/finplan/infrastructure/db/rls.py`.** Функция, которая в текущей
   транзакции сессии выставляет `app.user_id`. Выполняется через
   `SELECT set_config('app.user_id', :user_id, true)` с параметром, а не
   форматированием строки: `SET LOCAL` не принимает bind-параметров, а
   подстановка значения в текст SQL открывает инъекцию. Третий аргумент
   `true` делает значение локальным для транзакции, как `SET LOCAL` из 4.5.

2. **Репозитории в `src/finplan/infrastructure/db/repositories/`.** По
   одному модулю на агрегат: `users.py`, `accounts.py`, `categories.py`,
   `transactions.py`. Классы `SqlAlchemyUserRepository` и так далее
   принимают `AsyncSession` в конструкторе, переводят строки ORM в
   доменные сущности и обратно; ORM-объекты наружу не отдаются. Правила:
   - каждый запрос по объекту фильтрует по `user_id` явно, даже при
     включённом RLS (4.5, ADR-008);
   - нарушение уникального ключа (`IntegrityError` с `UniqueViolation`)
     переводится в `DuplicateError` из портов; прочие ошибки БД не
     маскируются;
   - `UserRepository.get_by_telegram_id` выполняется только через функцию
     БД, а не прямым `SELECT` из `users`: запрос вида
     `select(UserModel).from_statement(text("SELECT * FROM find_user_by_telegram_id(:telegram_id)"))`
     с `telegram_id` через bind-параметр или эквивалент, возвращающий
     строку в ту же модель. Способ
     решён диспетчером: транзакция поиска идёт без `app.user_id`, и
     прямой `SELECT` под `finplan_app` вернёт пусто;
   - `TransactionRepository.mark_reversed` выполняет `UPDATE` только
     столбца `status` с условием `status = 'posted'`; другой `UPDATE` и
     `DELETE` по `transactions` запрещены триггером (4.2);
   - `last_reversible` — по `created_at` по убыванию, `status = 'posted'`,
     `reverses_id IS NULL`, заданный `source`.

3. **`src/finplan/infrastructure/db/uow.py`.** `SqlAlchemyUnitOfWork`
   реализует протокол `UnitOfWork`, `SqlAlchemyUnitOfWorkFactory` —
   протокол `UnitOfWorkFactory`. Фабрика принимает
   `async_sessionmaker[AsyncSession]` и
   `ledger_factory: Callable[[AsyncSession], LedgerQueries]`, где
   `LedgerQueries` — протокол из портов. Реализацию `LedgerQueries`
   пишет 9b, а подставит её `container.py`, поэтому `uow.py` не
   импортирует ничего из `infrastructure/db/queries/`. Решение принято
   диспетчером ради параллельности 9a и 9b.

   Поведение:
   - `__aenter__` открывает сессию и транзакцию; при `user_id` не `None`
     первым запросом транзакции вызывает функцию из пункта 1;
   - репозитории и `ledger` создаются на одной сессии;
   - `__aexit__` откатывает транзакцию, если `commit` не вызывался, и
     закрывает сессию в любом случае;
   - `commit` и `rollback` делегируют сессии. Если после `commit` в том
     же блоке понадобится новая транзакция, `app.user_id` должен быть
     выставлен заново — либо это явно запрещено исключением. Что выбрано,
     записать в результат.

4. **`container.py` не трогать.** Подключение фабрики к контейнеру — в
   подзадачах entrypoints.

5. **Проверка типов.** Добавить в каждый модуль репозиториев и в
   `uow.py` строку, которая заставляет `mypy` сверить класс с протоколом
   без запуска, например
   `_check: type[UserRepository] = SqlAlchemyUserRepository` под
   `if TYPE_CHECKING:`, либо аннотированную фабрику. Способ — на
   усмотрение исполнителя, но проверка должна падать в `mypy` при
   расхождении сигнатур.

## Границы

- `src/finplan/domain/` и `src/finplan/application/` не изменяются.
  Если порт не реализуется без правки — вопрос диспетчеру.
- `src/finplan/infrastructure/db/queries/` не создаётся и не правится —
  это 9b.
- Модели и миграции не изменяются.
- `docs/architecture.md` не правится.
- `src/finplan/container.py` и `entrypoints/` не изменяются.
- Интеграционные тесты репозиториев не пишутся — это подзадача 10.
  Допустима одна ручная проверка против PostgreSQL из testcontainers,
  результат называется в отчёте.
- `.env` не правится. Коммиты не делаются.

## Критерий приёмки

- существуют `infrastructure/db/rls.py`, `infrastructure/db/uow.py` и
  четыре модуля в `infrastructure/db/repositories/`;
- `uv run mypy src` зелёный, и проверка из пункта 5 есть в каждом модуле;
- `grep -rn "infrastructure.db.queries" src/finplan/infrastructure/db/uow.py`
  пуст;
- `grep -n "find_user_by_telegram_id" src/finplan/infrastructure/db/repositories/users.py`
  непуст, а в `get_by_telegram_id` нет условия на столбец
  `telegram_id` модели;
- `make test` и `make lint` зелёные. Если `make lint` падает только на
  незаконченных файлах параллельной 9b, это называется в отчёте с
  решающей строкой вывода, а чужие файлы не правятся;
- `git diff --stat -- src/finplan/domain src/finplan/application` пуст.

## Результат исполнителя

**Сделано.** Реализован слой доступа к данным поверх ORM-моделей этапа 1.
`infrastructure/db/rls.py` выставляет `app.user_id` в текущей транзакции
через `SELECT set_config('app.user_id', :user_id, true)` — с
bind-параметром, без форматирования строки. Четыре репозитория
(`repositories/users.py`, `accounts.py`, `categories.py`,
`transactions.py`) переводят доменные сущности в строки ORM и обратно,
каждый запрос по объекту фильтрует по `user_id` явно (второй рубеж поверх
RLS, ADR-008), а нарушение уникального ключа (`sqlstate = 23505`)
переводится в `DuplicateError`; прочие ошибки БД пробрасываются как есть.
`UserRepository.get_by_telegram_id` идёт только через
`SELECT * FROM find_user_by_telegram_id(:telegram_id)` — прямого условия
на столбец `telegram_id` модели в коде нет. `TransactionRepository.
mark_reversed` — точечный `UPDATE ... SET status = 'reversed' WHERE
status = 'posted'`, `last_reversible` — по `created_at DESC`,
`status = 'posted'`, `reverses_id IS NULL`, заданный `source`.
`infrastructure/db/uow.py` даёт `SqlAlchemyUnitOfWork` и
`SqlAlchemyUnitOfWorkFactory`: `__aenter__` создаёт сессию, при известном
`user_id` первым запросом транзакции выставляет `app.user_id` (транзакция
у `AsyncSession` открывается лениво, на первом запросе — autobegin),
создаёт все четыре репозитория и `ledger` на этой же сессии; `__aexit__`
откатывает транзакцию, если не было явного `commit()`, и в любом случае
закрывает сессию. Во всех пяти новых модулях есть проверка соответствия
протоколу под `if TYPE_CHECKING: _check: type[Protocol] = Implementation`.

**Проверка.** `uv run mypy src` — `Success: no issues found in 89 source
files`. `uv run ruff check` и `uv run ruff format --check` — чисто.
`make test` — `158 passed`, без новых тестов: интеграционные тесты
репозиториев — подзадача 10, а модульных тестов на инфраструктуру этапа не
предусмотрено. `make lint` зелёный целиком (`build-brief.py --check`,
`ruff check`, `ruff format --check`, `mypy src`) — падений на файлах
параллельной 9b не было, `infrastructure/db/queries/ledger.py` уже
существовал на момент проверки и в сборку не мешал. Ручная проверка против
PostgreSQL из testcontainers пройдена: временный файл
`tests/integration/repositories/_manual_check.py` (регистрация
пользователя со счётом и дефолтными категориями через `RegisterUser`-подобный
сценарий напрямую через `UnitOfWork`, чтение через `get`/`list`/
`get_by_telegram_id`, изоляция от чужого `user_id` под RLS и явным
фильтром, `DuplicateError` на повторный `telegram_id`, запись и чтение
операции, `last_reversible` → `mark_reversed` → добавление сторно, повторный
`commit()` → `RuntimeError`) — `1 passed`, файл удалён после прогона, в
дереве не остался. `git diff --stat -- src/finplan/domain
src/finplan/application` пуст.

**Решения и отложенное.**
- Повторный `commit()` в одном экземпляре `SqlAlchemyUnitOfWork` запрещён
  явно `RuntimeError`, а не поддержан переустановкой `app.user_id`: раздел
  2.2 отводит `UnitOfWork` одну транзакцию на один вызов use case, и
  молчаливая переустановка `app.user_id` после `commit()` спрятала бы
  нарушение этого контракта, а не обслужила бы реальный сценарий — ни один
  текущий use case не коммитит дважды в одном блоке.
- Класс-уровневые аннотации `SqlAlchemyUnitOfWork.users/accounts/
  categories/transactions` объявлены типами протоколов
  (`UserRepository` и так далее), а не конкретными классами реализации:
  `mypy` сверяет мутируемые атрибуты протокола инвариантно, и аннотация
  конкретным классом ломала бы `type[UnitOfWork] = SqlAlchemyUnitOfWork`
  под `TYPE_CHECKING`, хотя каждый репозиторий сам по себе протоколу
  соответствует.
- Восстановление `Currency` для доменных сущностей — `Account`, `User`,
  `Transaction` — идёт через `JOIN`/дозапрос к таблице `currencies` за
  `minor_unit` по коду, а не через статический словарь по образцу
  `_CURRENCIES` в `RegisterUser`: справочник валют — источник истины в БД
  и меняется миграцией, дублировать его в нескольких местах
  инфраструктуры не хотелось.
- Три административных поля ORM без источника в домене заполнены в
  инфраструктуре без запроса диспетчеру, так как ни один сценарий их не
  читает обратно через порт: `users.updated_at` при `add()` = значению
  `created_at` (домен `User` не хранит момент обновления, метода
  обновления в порту нет); `accounts.created_at` (не имеет
  `server_default`, в отличие от `users`/`transactions`) = `datetime.
  now(UTC)` в момент вставки; `transactions.transfer_group_id` = `NULL`
  всегда, поскольку `RecordTransaction` этапа 1 переводов не создаёт, а
  домен `Transaction` это поле не хранит.
- `transactions.occurred_on` (`NOT NULL`, по разделу 4.3 — «дата в
  таймзоне пользователя, денормализованная для группировок») заполняется
  как календарная дата `transaction.occurred_at` без учёта таймзоны
  пользователя: сущность `Transaction` таймзону не хранит, а
  `RecordTransaction` тоже её не читает при простановке `occurred_at`.
  Ни `LedgerQueries` подзадачи 9b (работает через `occurred_at`), ни один
  другой текущий потребитель `occurred_on` не читает, поэтому это не
  блокирует приёмку, но расходится с текстом раздела 4.3 буквально.
  Решение не архитектурное само по себе (просто самая простая корректная
  подстановка non-null колонки, которую сейчас никто не читает), но
  правильная его отмена, вероятно, потребует протащить таймзону
  пользователя через `Transaction.new`/`RecordTransaction` — то есть
  правку `application`/`domain`, которая не входит в границы этой задачи.
  Вынесено в вопрос диспетчеру ниже.

**Вопросы диспетчеру.**
- `transactions.occurred_on` нуждается в дате по таймзоне пользователя
  (раздел 4.3), а не по UTC `occurred_at`, как только появится первый
  реальный потребитель этой колонки (отчёты/лента по календарным дням).
  Нужно решение, откуда репозиторий возьмёт `User.timezone` в момент
  `add()`: либо `Transaction`/`RecordTransaction` начинают явно нести
  локальную дату (правка `domain`/`application`), либо
  `TransactionRepository.add` получает её отдельным параметром или
  дозапросом к `users` в той же транзакции. Ни то ни другое не входит в
  границы этой подзадачи, поэтому `occurred_on` пока заполнен по UTC-дате
  `occurred_at` — рабочий, но временный вариант.
- В рабочем дереве в процессе задачи менялись `docs/architecture.md` и
  `docs/architecture-brief.md` (раздел про кросс-валютный перевод,
  строки около 693–706) — эта правка не моя и, судя по содержанию, от
  параллельной подзадачи 9b/её ревью; называю на всякий случай, чтобы не
  потерялась при сведении веток.
