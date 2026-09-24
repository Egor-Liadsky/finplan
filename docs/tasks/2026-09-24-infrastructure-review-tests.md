# Тесты по находкам ревью инфраструктуры этапа 1

- **Исполнитель:** tester
- **Слой:** infrastructure, domain, application (только тесты)
- **Раздел архитектуры:** docs/architecture.md, разделы 3.1, 3.3, 4.2, 4.3, 5.7, 11.1
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 11e плана `docs/tasks/2026-09-23-stage1-plan.md`. Ревью
инфраструктуры (подзадачи 11a–11d, файлы
`docs/tasks/2026-09-24-infrastructure-*-review.md`) нашло пробелы в тестах и
два дефекта кода. Дефекты кода диспетчер исправил сам, тесты на них не
написаны:

- `LedgerQueries.account_movements`
  (`src/finplan/infrastructure/db/queries/ledger.py`) теперь учитывает
  `kind = interest` со знаком плюс по `account_id`, как требует формула
  остатка в 5.7; раньше такие операции в остаток не попадали;
- `SqlAlchemyTransactionRepository.add`
  (`src/finplan/infrastructure/db/repositories/transactions.py`) различает
  два уникальных ключа `transactions`: при нарушении
  `uq_transactions_reverses_id` поднимается `DuplicateError` с текстом
  «операция <id> уже сторнирована», а не текст про `external_key`.

`uv run pytest -q` — 210 passed, `make lint` зелёный на рабочем дереве с
этими правками.

До первой правки прочитать:

- `docs/architecture-brief.md` целиком;
- `docs/architecture.md` через `Read` с `offset` и `limit` по карте в
  выжимке: из 3.3 — правила `occurred_on` и абзац «Форма сторно»; 4.2;
  из 5.7 — формула остатка; из 3.1 — «Мультивалютность в операциях»;
- `tests/integration/repositories/conftest.py` — фикстуры `uow_factory` и
  `make_transaction`; тесты работают под ролью `finplan_app` внутри
  внешней транзакции, которая не коммитится;
- разделы «Результат исполнителя» в файлах 11b, 11c и 11d — там находки с
  `file:line`.

## Задание

Дописать тесты, закрывающие находки ревью:

1. `occurred_on` в таймзоне с отрицательным смещением от UTC, например
   `America/New_York` или `America/Los_Angeles`: операция, у которой в UTC
   уже следующий день, а у пользователя ещё текущий, получает дату
   текущего дня. Проверка на всех трёх уровнях, где сейчас есть тест на
   Москву: `tests/unit/domain/test_transaction.py`,
   `tests/unit/application/test_record_transaction.py`,
   `tests/integration/repositories/test_transactions.py`.
2. Вторая сторнирующая запись с тем же `reverses_id` даёт `DuplicateError`,
   и текст ошибки говорит о повторном сторно, а не об `external_key`, —
   `tests/integration/repositories/test_transactions.py`.
3. Операция `kind = interest` со статусом `posted` увеличивает результат
   `account_movements` по своему `account_id`; сторнированная —
   не увеличивает. Файл `tests/integration/repositories/test_ledger_queries.py`.
4. `totals_by_category` суммирует `base_amount`, а не `amount`: операция по
   счёту в валюте, отличной от базовой, с `base_amount != amount` —
   `tests/integration/repositories/test_ledger_queries.py`.
5. Триггер `trg_transactions_immutable` по 4.2: `UPDATE` любого столбца
   строки журнала, кроме перехода `status` из `posted` в `reversed`, и
   `DELETE` строки отклоняются базой. Проверять прямым SQL под ролью
   `finplan_app` в той же внешней транзакции; ожидаемую ошибку назвать
   точно (класс исключения или SQLSTATE), а не любым исключением. После
   ожидаемой ошибки внутри транзакции нужен откат к `SAVEPOINT`, иначе
   следующая команда упадёт с `InFailedSqlTransaction` — это учесть в
   тесте, а не в фикстурах других тестов. Файл
   `tests/integration/repositories/test_transactions.py`.

Если параметризованный тест изоляции из
`tests/integration/repositories/test_tenant_isolation.py` падает из-за
новых тестов — это ошибка новых тестов, а не повод менять изоляцию.

## Границы

- `src/`, `migrations/`, `docs/architecture.md`, `docs/dev-log.md` не
  изменяются — проверяется `git diff --stat -- src migrations docs/architecture.md docs/dev-log.md`
  относительно состояния на момент запуска;
- правятся только файлы тестов, названные в задании, и при необходимости
  `tests/integration/repositories/conftest.py` — только добавлением
  параметров фикстуры `make_transaction`, без изменения поведения
  существующих вызовов;
- `float` в литералах сумм не используется;
- если тест выявляет дефект продуктового кода, код не чинится: тест
  помечается `xfail(strict=True)` с причиной, а дефект описывается в
  «Вопросах диспетчеру».

## Критерий приёмки

- `uv run pytest -q` зелёный, число тестов больше 210;
- `make lint` зелёный;
- на каждый из пяти пунктов задания есть хотя бы один тест, названный в
  отчёте с `file:line`;
- проверка каждого нового теста на «красноту»: в отчёте для пунктов 2 и 3
  сказано, что тест падает при откате соответствующей правки диспетчера
  (проверить временным откатом через `git stash` только файла в `src/`,
  затем вернуть; итоговый `git diff -- src` совпадает с исходным).

## Результат исполнителя

_Заполняет исполнитель. Выше этой строки ничего не меняется._
