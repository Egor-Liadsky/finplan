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
