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

**Сделано.** Дописаны тесты на пять находок ревью 11a–11d — все пять пунктов
задания закрыты минимум одним тестом:

1. `occurred_on` при отрицательном смещении от UTC (`America/Los_Angeles`,
   UTC-7 в сентябре): операция в `2026-09-24 02:30 UTC` получает
   `occurred_on = 2026-09-23`, дату, ещё текущую по местному времени, —
   `tests/unit/domain/test_transaction.py:233`,
   `tests/unit/application/test_record_transaction.py:104`,
   `tests/integration/repositories/test_transactions.py:181`. Раньше в
   этих трёх файлах была только проверка положительного смещения
   (`Europe/Moscow`), которая не поймала бы регрессию в знаке смещения.
2. Вторая сторнирующая запись с тем же `reverses_id` даёт `DuplicateError`
   с текстом про повторное сторно, без упоминания `external_key` —
   `tests/integration/repositories/test_transactions.py:223`.
3. `kind = interest` со статусом `posted` прибавляется к `account_movements`
   по своему `account_id`; сторнированная пара (обе строки `status =
   reversed`) в сумму не входит — `tests/integration/repositories/
   test_ledger_queries.py:188` и `:219`.
4. `totals_by_category` суммирует `base_amount`, а не `amount`: операция в
   USD (`amount = 100.0000`) со снимком в RUB (`base_amount = 9500.0000`)
   даёт в отчёте `9500.0000` — `tests/integration/repositories/
   test_ledger_queries.py:422`.
5. Триггер `trg_transactions_immutable`: `UPDATE` столбца, отличного от
   `status`, и `DELETE` строки журнала отклоняются PostgreSQL с
   `SQLSTATE = P0001` (`raise_exception`, код по умолчанию для `RAISE
   EXCEPTION` без явного `SQLSTATE` в `fn_transactions_guard_immutable`) —
   `tests/integration/repositories/test_transactions.py:365` и `:396`.
   Обе проверки идут прямым SQL на `app_connection` под ролью
   `finplan_app`, каждая — в собственном `begin_nested()` (вложенный
   `SAVEPOINT`), который откатывается в `finally` после ожидаемой ошибки;
   `DELETE`-тест дополнительно читает строку через репозиторий после
   отката и убеждается, что она осталась на месте.

`tests/integration/repositories/conftest.py` менять не потребовалось:
фикстура `make_transaction` уже принимала `timezone`, `base_amount`,
`base_currency`, `base_rate` через `**overrides`/именованные параметры.

**Проверка.** `uv run pytest -q` — 219 passed (было 210, добавлено 9
тестов); `uv run ruff check` — чисто; `uv run mypy src` — чисто;
`make lint` целиком (включая `docs/build-brief.py --check` и `ruff format
--check`) — зелёный. Красный прогон подтверждён для пунктов 2 и 3
критерия приёмки: временный откат `src/finplan/infrastructure/db/queries/
ledger.py` и `src/finplan/infrastructure/db/repositories/transactions.py`
к состоянию до коммита `4715da4` (`git checkout 4715da4~1 -- <файлы>`)
даёт красными ровно `test_second_reversal_of_same_original_raises_
duplicate_error_about_reversal` (падает с `AssertionError: операция с
external_key None уже сохранена` вместо ожидаемого текста про сторно) и
`test_posted_interest_adds_to_account_by_account_id` (падает с `KeyError`
— счёт не попадает в словарь, `interest` в сумму не учитывается); третий
новый тест в том же файле, `test_reversed_interest_does_not_add_to_
account`, при этом откате остаётся зелёным — ожидаемо, потому что оба
поведения (учитывать и не учитывать `interest`) дают одинаковый результат
для сторнированной пары, которая не попадает в сумму в любом случае, это
не пункт 3 критерия приёмки, а отдельная проверка на «не ломает то, что и
так работало». После проверки `git checkout HEAD -- <файлы>` вернул `src`
к исходному состоянию; `git diff --stat -- src migrations
docs/architecture.md docs/dev-log.md` после этого пуст.

**Решения и отложенное.**

- Пункт 4 задания (`totals_by_category` суммирует `base_amount`) —
  тест на уже корректное поведение, не на дефект: в текущем
  `SqlAlchemyLedgerQueries.totals_by_category`
  (`src/finplan/infrastructure/db/queries/ledger.py:92`) `func.sum`
  и так берёт `TransactionRow.base_amount`, а не `TransactionRow.amount`.
  Тест написан как контрольный пример раздела 11.2 (операция с
  `amount != base_amount`, сверка через `Decimal`), а не как `xfail`:
  граница задания требует `xfail(strict=True)` только для тестов, которые
  ловят дефект, а этот дефекта не ловит.
- SQLSTATE `P0001` подтверждён эмпирически прогоном тестов против
  контейнера PostgreSQL 16 (Docker был доступен в этой сессии), а не
  предположен по документации — оба теста триггера сначала прошли на
  текущем коде и только затем строка `assert sqlstate == "P0001"`
  зафиксирована как ожидание.
- Для пункта 5 выбраны ровно два минимальных сценария из задания —
  `UPDATE` постороннего столбца (`comment`) при `status`, не меняющемся с
  `posted` на `reversed`, и `DELETE`. Переход `status: posted -> pending`
  или `reversed -> posted` отдельно не проверялся: он покрывается той же
  веткой `IF OLD.status <> 'posted' OR NEW.status <> 'reversed'` в
  `fn_transactions_guard_immutable`, что и выбранный сценарий, и не назван
  в задании отдельно.

**Вопросы диспетчеру.** Нет.
