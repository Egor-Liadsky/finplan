# Запись и чтение `occurred_on` в репозитории операций

- **Исполнитель:** developer
- **Слой:** infrastructure
- **Раздел архитектуры:** docs/architecture.md, раздел 3.3 (сущность `Transaction`, последний пункт инвариантов про `occurred_on`), 4.3 (таблица `transactions`, столбец `occurred_on`)
- **Заведена:** 2026-09-24

## Входные условия

Третья подзадача 9c плана `docs/tasks/2026-09-23-stage1-plan.md`.
Подзадача domain (`docs/tasks/done/2026-09-24-transaction-occurred-on-domain.md`)
закрыта: у `Transaction` есть поле `occurred_on: date`, вычисленное в
таймзоне пользователя. Репозиторий из подзадачи 9a пока пишет в столбец
`occurred_on` календарную дату `occurred_at` в UTC и оставил об этом
комментарий. Параллельно идёт подзадача application
(`docs/tasks/2026-09-24-transaction-occurred-on-application.md`); эта
задача её не читает.

До первой правки прочитать:

- `src/finplan/domain/entities/transaction.py`, поле `occurred_on`;
- `src/finplan/infrastructure/db/repositories/transactions.py`: метод
  `add` (строки около 45–75) и функцию преобразования модели в сущность
  (строки около 135–165).

## Задание

1. В `add` писать `occurred_on=transaction.occurred_on` и удалить
   комментарий о расхождении с разделом 4.3 — расхождения больше нет.
2. При чтении модели в сущность передавать
   `occurred_on=model.occurred_on`.
3. Поискать `occurred_at.date()` в остальных файлах
   `src/finplan/infrastructure/`; найденное назвать в результате, не
   править, если оно не относится к `transactions.occurred_on`.

## Границы

- Изменяется только `src/finplan/infrastructure/db/repositories/transactions.py`.
- Миграции, ORM-модели, `domain/` и `application/` не трогать: столбец
  `occurred_on` в таблице уже есть.
- Тесты не пишутся: интеграционные тесты репозиториев — подзадача 10.

## Критерий приёмки

- `uv run mypy src/finplan/infrastructure` без ошибок;
- `uv run ruff check` и `uv run ruff format --check` по изменённому файлу
  чистые;
- в `transactions.py` нет вызова `occurred_at.date()` и комментария о
  расхождении с 4.3;
- `git diff --stat` показывает изменение одного файла.

## Результат исполнителя

Исполнитель: главная сессия. Правка уложилась в две строки одного файла,
а по `CLAUDE.md` такую правку дешевле сделать самому, чем заводить запуск.

**Сделано.** Метод `add` репозитория операций пишет в столбец
`occurred_on` поле `Transaction.occurred_on`, вычисленное доменом в
таймзоне пользователя; комментарий о расхождении с разделом 4.3 удалён.
Преобразование модели в сущность передаёт `occurred_on=model.occurred_on`.

**Проверка.** `uv run mypy src/finplan/infrastructure` — без ошибок в 24
файлах; `uv run ruff check` и `uv run ruff format --check` по файлу —
чисто. Поиск `occurred_at.date()` в `src/finplan/infrastructure/` ничего
не нашёл.

**Решения и отложенное.** Проверка против PostgreSQL не делалась: это
подзадача 10.

**Вопросы диспетчеру.** Нет.
