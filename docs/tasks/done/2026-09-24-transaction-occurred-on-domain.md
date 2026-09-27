# `occurred_on` в доменной `Transaction`

- **Исполнитель:** developer
- **Слой:** domain
- **Раздел архитектуры:** docs/architecture.md, раздел 3.3 (сущность `Transaction`: таблица атрибутов и абзацы «Инварианты», включая «Форма сторно» и последний пункт про `occurred_on`), 4.3 (таблица `transactions`, столбец `occurred_on`), 2.2
- **Заведена:** 2026-09-24

## Входные условия

Это первая из трёх подзадач 9c плана `docs/tasks/2026-09-23-stage1-plan.md`.
Решение принято диспетчером и записано в раздел 3.3: `Transaction` хранит
поле `occurred_on: date` — календарную дату `occurred_at` в таймзоне
пользователя; `Transaction.new` вычисляет его сам из `occurred_at` и
переданного `tzinfo`. Следом идут две подзадачи, которые опираются на
результат этой: application (`RecordTransaction` передаёт таймзону) и
infrastructure (репозиторий пишет и читает поле).

До первой правки прочитать:

- `docs/architecture-brief.md`;
- `docs/architecture.md` через `Read` с `offset` и `limit` по карте из
  выжимки: из 3.3 — только сущность `Transaction` (таблица и инварианты);
- `src/finplan/domain/entities/transaction.py`;
- `tests/unit/domain/test_transaction.py`.

## Задание

1. **Поле.** В `Transaction` добавить `occurred_on: date` сразу после
   `occurred_at`.
2. **`Transaction.new`.** Новый обязательный keyword-аргумент
   `timezone: tzinfo` (тип из модуля `datetime`; `zoneinfo` в домене не
   импортировать — разбор IANA-имени остаётся за `application`).
   `occurred_on = occurred_at.astimezone(timezone).date()`. Если
   `occurred_at` без таймзоны (`occurred_at.tzinfo is None`) —
   `InvariantViolationError`: дата из наивного момента неоднозначна.
3. **Сторно.** `reverse` копирует `occurred_on` исходной — через
   `replace` это получается само; проверить, что так и есть.
4. **Тесты домена.** Обновить `tests/unit/domain/test_transaction.py`
   под новую сигнатуру и добавить проверки: момент `2026-09-23T22:30Z`
   при `timezone = ZoneInfo("Europe/Moscow")` даёт `occurred_on =
   2026-09-24`, а при `timezone = UTC` — `2026-09-23`; наивный
   `occurred_at` отклоняется; сторнирующая запись несёт `occurred_on`
   исходной.

## Границы

- Файлы вне `src/finplan/domain/` и `tests/unit/domain/` не изменяются.
  После этой подзадачи `mypy` и тесты `application` ожидаемо падают на
  вызове `Transaction.new` без `timezone` — это чинит следующая
  подзадача, здесь не трогать.
- Другие сущности и сигнатуры домена не меняются.

## Критерий приёмки

- `uv run pytest tests/unit/domain -q` зелёный, новые проверки из
  пункта 4 среди них;
- `uv run mypy src/finplan/domain` без ошибок;
- `uv run ruff check src/finplan/domain tests/unit/domain` и
  `uv run ruff format --check` по тем же путям чистые;
- `git diff --stat` показывает изменения только в двух названных
  каталогах.

## Результат исполнителя

- **Сделано.** В `Transaction` добавлено поле `occurred_on: date` сразу
  после `occurred_at`. `Transaction.new` получил обязательный
  keyword-аргумент `timezone: tzinfo` (импорт из `datetime`, `zoneinfo`
  в домене не используется); при `occurred_at.tzinfo is None` бросается
  `InvariantViolationError` — наивный момент не даёт однозначной даты;
  иначе `occurred_on = occurred_at.astimezone(timezone).date()`.
  `reverse` менять не пришлось: он строит обе записи через
  `dataclasses.replace(self, ...)`, поэтому `occurred_on` копируется в
  сторнирующую запись автоматически вместе с `occurred_at`, это только
  проверено тестом. `_make_transaction` в тестах (прямой конструктор
  `Transaction`, минуя `.new`) получил параметр `occurred_on` с
  дефолтом — дата `occurred_at` в UTC. Добавлены три новые проверки:
  `occurred_on` по `Europe/Moscow` и по `UTC` для одного и того же
  `occurred_at = 2026-09-23T22:30Z` дают разные даты (`2026-09-24` и
  `2026-09-23`), наивный `occurred_at` отклоняется, сторнирующая запись
  несёт `occurred_on` исходной (явная проверка значения `date(2026, 9,
  24)`, не только равенство).
- **Проверка.** `uv run pytest tests/unit/domain -q` — 108 passed.
  `uv run mypy src/finplan/domain` — Success, no issues found in 13
  source files. `uv run ruff check src/finplan/domain tests/unit/domain`
  — All checks passed (после удаления лишнего `# noqa: DTZ001` — правило
  не включено в конфиге ruff проекта). `uv run ruff format --check` по
  тем же путям — 20 files already formatted. `git diff --stat -- src/finplan/domain tests/unit/domain`
  показывает изменения ровно в `transaction.py` обоих каталогов;
  `docs/architecture-brief.md`, `docs/architecture.md` и
  `docs/tasks/2026-09-23-stage1-plan.md` были изменены диспетчером до
  начала этой подзадачи (зафиксировано в git status на старте сессии),
  этой работой не тронуты.
- **Решения и отложенное.** Сигнатура `.new` расширена только
  обязательным `timezone`; порядок и типы прочих параметров не менялись.
  Следующая подзадача (application) обязана передавать `timezone`, иначе
  `RecordTransaction` не соберётся — это ожидаемо и оговорено в задании.
- **Вопросы диспетчеру.** Нет.
