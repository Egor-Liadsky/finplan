# Таймзона пользователя в `RecordTransaction`

- **Исполнитель:** developer
- **Слой:** application
- **Раздел архитектуры:** docs/architecture.md, раздел 3.3 (сущность `Transaction`, последний пункт инвариантов про `occurred_on`), 2.2 (абзац «Контракт портов и граница транзакции»)
- **Заведена:** 2026-09-24

## Входные условия

Вторая подзадача 9c плана `docs/tasks/2026-09-23-stage1-plan.md`.
Подзадача domain (`docs/tasks/done/2026-09-24-transaction-occurred-on-domain.md`)
закрыта: у `Transaction` есть поле `occurred_on: date`, а
`Transaction.new` принимает обязательный keyword-аргумент
`timezone: tzinfo` и вычисляет `occurred_on` сам. Сейчас `mypy` и тесты
`application` падают на вызовах `Transaction.new` без `timezone` — это и
чинится здесь. Параллельно идёт подзадача infrastructure
(`docs/tasks/2026-09-24-transaction-occurred-on-infrastructure.md`);
эта задача её не читает.

До первой правки прочитать:

- `docs/architecture-brief.md`;
- из `docs/architecture.md` по карте из выжимки — последний пункт
  инвариантов `Transaction` в 3.3;
- `src/finplan/domain/entities/transaction.py`, метод `new`;
- `src/finplan/application/use_cases/transactions/record_transaction.py`;
- `src/finplan/application/use_cases/auth/register_user.py`, строки
  40–60: там уже разбирается IANA-имя через `ZoneInfo` — образец;
- `src/finplan/application/dto/transactions.py`;
- `tests/unit/application/conftest.py`, фикстура `make_transaction`.

## Задание

1. **`RecordTransaction`.** Передать в `Transaction.new` аргумент
   `timezone=ZoneInfo(user.timezone)`. Неизвестное имя таймзоны у уже
   сохранённого пользователя — не ошибка команды, а повреждённые
   данные: не перехватывать `ZoneInfoNotFoundError`, пусть поднимается.
2. **`TransactionDTO`.** Добавить `occurred_on: date` после
   `occurred_at` и заполнять из сущности: бот покажет пользователю дату
   записи именно в его таймзоне.
3. **Тесты.** В фикстуре `make_transaction` добавить параметр
   `timezone: tzinfo = UTC` и передавать его в `Transaction.new`.
   Добавить тест `RecordTransaction`: пользователь с таймзоной
   `Europe/Moscow`, `occurred_at = 2026-09-23T22:30Z`, в результате
   `occurred_on == date(2026, 9, 24)`.

## Границы

- Изменяются только `src/finplan/application/` и `tests/unit/application/`.
- `domain/` и `infrastructure/` не трогать.
- Сигнатура `RecordTransactionCommand` не меняется.

## Критерий приёмки

- `make lint` зелёный, если подзадача infrastructure к этому моменту
  тоже закрыта; иначе `uv run mypy src/finplan/domain src/finplan/application`
  без ошибок;
- `uv run pytest tests/unit -q` зелёный, новый тест среди них;
- `git diff --stat` показывает изменения только в двух названных
  каталогах.

## Результат исполнителя

- **Сделано.** `RecordTransaction` передаёт в `Transaction.new` таймзону
  пользователя `timezone=ZoneInfo(user.timezone)`; `ZoneInfoNotFoundError`
  не перехватывается и поднимается наверх — рядом оставлен комментарий,
  что это повреждённые данные, а не ошибка команды. `TransactionDTO`
  получил поле `occurred_on: date` сразу после `occurred_at`, заполняется
  из сущности в `from_entity`. Фикстура `make_transaction` в
  `tests/unit/application/conftest.py` получила параметр
  `timezone: tzinfo = UTC` и передаёт его в `Transaction.new`. Добавлен
  тест `test_occurred_on_is_computed_in_user_timezone`: пользователь с
  таймзоной `Europe/Moscow`, `occurred_at = 2026-09-23T22:30Z` (часы
  переведены вперёд через `clock.set`, иначе сработал бы инвариант «не
  более чем на сутки в будущем» относительно фиксированного `NOW`
  фикстуры `clock`), результат `occurred_on == date(2026, 9, 24)`.
- **Проверка.** `uv run pytest tests/unit -q` — 153 passed. К моменту
  проверки подзадача infrastructure уже была закрыта диспетчером
  (`docs/tasks/done/2026-09-24-transaction-occurred-on-infrastructure.md`),
  поэтому прогнан полный `make lint`: `build-brief.py --check`, `ruff
  check`, `ruff format --check`, `uv run mypy src` — все зелёные (89
  файлов). Точечно перед этим отдельно проверялся
  `uv run mypy src/finplan/domain src/finplan/application` — тоже
  зелёный.
- **Решения и отложенное.** Комментарий в use case о непойманном
  `ZoneInfoNotFoundError` добавлен намеренно — в задании явно требовалось
  не перехватывать исключение, и это отличается от `RegisterUser`, где
  оно перехватывается и превращается в `InvalidCommandError`: там
  таймзону вводит пользователь, здесь она уже сохранена в БД. `git diff
  --stat` по всему репозиторию показывает файлы из параллельных
  подзадач (`domain/entities/transaction.py`,
  `infrastructure/db/repositories/transactions.py`, `docs/architecture*`,
  план этапа) — они не относятся к этой задаче; изменения именно этого
  исполнителя ограничены `src/finplan/application/` и
  `tests/unit/application/` (проверено отдельным
  `git diff --stat -- src/finplan/application tests/unit/application`).
- **Вопросы диспетчеру.** Нет.
