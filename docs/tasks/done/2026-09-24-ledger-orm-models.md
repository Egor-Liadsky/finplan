# ORM-модели и миграция таблиц accounts, categories, transactions

- **Исполнитель:** developer
- **Слой:** infrastructure
- **Раздел архитектуры:** docs/architecture.md, разделы 4.1, 4.2, 4.3; для сверки полей — 3.3
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 8a плана `docs/tasks/2026-09-23-stage1-plan.md`. Подзадача 8
разбита на две по объёму: здесь только таблицы, а роли базы, RLS и функция
поиска пользователя — в следующей подзадаче 8b
(`docs/tasks/2026-09-24-rls-and-db-roles.md`), которая запускается после
этой.

Готово: слои `domain` и `application` этапа 1; модели `users` и
`currencies` в `src/finplan/infrastructure/db/models/` и миграция
`migrations/versions/20260921_1730-fc2037cdf9d2_create_currencies_and_users.py`.
На `e203cb6` в раздел 4.3 добавлен столбец `categories.aliases text[]`, а в
доменную `Category` — поле `aliases`. `make test` (156 passed) и `make lint`
зелёные.

До первой правки прочитать:

- `docs/architecture-brief.md` — карта документа и правила схемы БД;
- `docs/architecture.md` через `Read` с `offset` и `limit` по карте из
  выжимки: 4.1, 4.2, из 4.3 — таблицы `accounts`, `categories`,
  `transactions`;
- `src/finplan/infrastructure/db/base.py`,
  `src/finplan/infrastructure/db/models/users.py` — образец стиля моделей;
- существующую миграцию — образец стиля миграций;
- `tests/integration/test_migrations.py`.

## Задание

1. Модели SQLAlchemy 2.x для `accounts`, `categories`, `transactions` в
   `src/finplan/infrastructure/db/models/` — по файлу на таблицу, как у
   `users.py`. Столбцы, типы, ограничения, имена ограничений и индексов —
   строго по таблицам раздела 4.3, включая частичный уникальный индекс
   `uq_accounts_user_id_name`, индекс с `text_pattern_ops` у `categories`
   и новый столбец `aliases text[] NOT NULL DEFAULT '{}'`. Деньги —
   `Numeric` с масштабом из 4.3, никогда `Float`.
2. Новая миграция Alembic поверх `fc2037cdf9d2`, создающая эти три таблицы
   со всеми ограничениями и индексами. `downgrade` удаляет их в обратном
   порядке. Если раздел 4.2 требует на уровне БД защиты журнала
   `transactions` от `UPDATE` и `DELETE`, она входит в эту миграцию.
3. Проверить `uv run alembic check` или автогенерацию вхолостую: модели и
   миграция не должны расходиться.

## Границы

- `src/finplan/domain/` и `src/finplan/application/` не изменяются.
- RLS, политики, роли, `GRANT` и функции `SECURITY DEFINER` здесь не
  делаются — это подзадача 8b.
- Репозитории, Unit of Work и запросы не пишутся — это подзадачи 9a и 9b.
- Таблицы, не названные в задании (`budgets`, `account_valuations` и
  прочие из 4.3), не создаются.
- `docs/architecture.md` не правится. Расхождение модели с документом или
  неясность документа — вопрос диспетчеру, а не решение на месте.

## Критерий приёмки

- `make up` и `make migrate` проходят;
- `uv run alembic downgrade -1`, затем `uv run alembic upgrade head`
  проходят;
- `tests/integration/test_migrations.py` зелёный, и тест проверяет
  появление трёх новых таблиц;
- `make test` и `make lint` зелёные.

## Результат исполнителя

**Сделано.** Добавлены ORM-модели `Account`, `Category`, `Transaction`
(`src/finplan/infrastructure/db/models/{accounts,categories,transactions}.py`)
и миграция `20260924_1500-2058c667ebfe_create_accounts_categories_transactions.py`
поверх `fc2037cdf9d2`, создающая три таблицы. Столбцы, типы, `CHECK`,
уникальные и частичные индексы, `text_pattern_ops` у `ix_categories_user_id_path`
и `aliases text[] NOT NULL DEFAULT '{}'` воспроизведены дословно по разделу
4.3. Для `transactions` в миграции заведена иммутабельность на уровне БД
(раздел 4.2/4.3): функция `fn_transactions_guard_immutable()` и триггер
`trg_transactions_immutable` на `BEFORE UPDATE OR DELETE` — `DELETE` запрещён
всегда, `UPDATE` разрешён только как переход `status` `posted → reversed`
без изменения прочих столбцов; поведение проверено вручную на реальной
dev-БД в `docker compose` (см. «Проверка»). `tests/integration/test_migrations.py`
дополнен проверкой появления/исчезновения `accounts`, `categories`,
`transactions` в цикле `upgrade → downgrade → upgrade`. `downgrade` удаляет
триггер, функцию и три таблицы в порядке, обратном созданию.

Столбцы `transactions.deposit_id`, `.goal_id`, `.recurring_rule_id`
заведены **без `ForeignKey`**: таблицы-цели `deposits`, `savings_goals`,
`recurring_rules` раздела 4.3 в эту подзадачу не входят (границы задания
это прямо запрещают) и появятся на более поздних этапах. Сами столбцы
нужны уже сейчас, потому что на них ссылается доменная сущность
`Transaction` (поля `recurring_rule_id`, `deposit_id`, `goal_id` из
подзадачи 1). Решение зафиксировано докстрингом модуля
`transactions.py` и комментарием в миграции; FK-ограничения должны
добавиться отдельной миграцией вместе с таблицами-целями.

**Проверка.**

- `uv run pytest -q` — 156 passed (включая `tests/integration/test_migrations.py`,
  который поднимает отдельный PostgreSQL 16 через `testcontainers`, гоняет
  `upgrade head → downgrade base → upgrade head` и `alembic check`).
- `uv run ruff check` — `All checks passed!`.
- `uv run ruff format --check` — после `uv run ruff format` на файле
  миграции все 118 файлов отформатированы.
- `uv run mypy src` — `Success: no issues found in 82 source files`.
- `python3 docs/build-brief.py --check` — `docs/architecture-brief.md`
  соответствует документу (не менялся).
- `make up` и `make migrate` в буквальном виде не прогонялись: `make migrate`
  на хосте резолвит `DATABASE_URL` из `.env` с хостом `postgres`
  (docker-внутренний DNS), с хоста он не резолвится (`socket.gaierror`) —
  это не связано с этой подзадачей, воспроизводится и на уже смигрированной
  на `fc2037cdf9d2` предыдущей ревизии базе. Docker-сервис `migrate` из
  `docker-compose.yml` пересобрать тоже не удалось: `docker compose run
  --rm --build migrate` падает на `error getting credentials - err: exec:
  "docker-credential-desktop": executable file not found in $PATH` при
  вытягивании `ghcr.io/astral-sh/uv:0.8` — проблема окружения хоста
  (Docker credential helper), не кода. Вместо этого миграция и её откат
  прогнаны напрямую через `uv run alembic upgrade head / check / downgrade
  -1 / upgrade head` с `DATABASE_URL=postgresql+asyncpg://finplan:finplan@localhost:5432/finplan`
  против уже поднятого `docker compose` Postgres (порт `5432` опубликован
  на хост) — все шаги прошли, `alembic check` не нашёл расхождений, база
  сейчас на `head` (`2058c667ebfe`). Дополнительно вручную через `psql`
  внутри контейнера проверено: `DELETE` из `transactions` падает с текстом
  триггера, произвольный `UPDATE` (смена `amount`) падает тоже, а переход
  `status: posted → reversed` проходит.

**Решения и отложенное.**

- FK у `deposit_id`, `goal_id`, `recurring_rule_id` в `transactions`
  осознанно не созданы (см. «Сделано») — единственный технически
  возможный вариант, раз целевые таблицы не входят в границы этой
  подзадачи; альтернатива (не заводить сами столбцы) сломала бы
  соответствие ORM-модели доменной сущности `Transaction` из подзадачи 1
  и репозитории подзадачи 9a, которым нужно маппить все её поля.
- Имя триггерной функции (`fn_transactions_guard_immutable`) документом не
  задано — выбрано по аналогии с именем триггера `trg_transactions_immutable`
  из раздела 4.3; сам раздел называет только триггер.
- `created_at` у `accounts` — без `server_default`, ровно как в таблице
  документа (в отличие от `users` и `transactions`, где `DEFAULT now()`
  указан явно); значение подставит репозиторий в подзадаче 9a.
- RLS, роли БД, `GRANT`, `SECURITY DEFINER` не делались — это подзадача 8b,
  как и обозначено в границах.

**Вопросы диспетчеру.** Нет. Расхождений кода с `docs/architecture.md` не
обнаружено; решение по отсутствующим FK выше — вынужденное (нет второго
технически валидного варианта), но диспетчер может захотеть явно
подтвердить его при заведении будущей миграции для `deposits`/
`savings_goals`/`recurring_rules`.
