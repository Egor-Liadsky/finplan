# Роли базы данных, политики RLS и функция поиска пользователя

- **Исполнитель:** developer
- **Слой:** infrastructure; конфигурация запуска
- **Раздел архитектуры:** docs/architecture.md, раздел 4.5 целиком; 10.1 — таблица переменных окружения; 10.3 — docker-compose; ADR-008 в 14.1
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 8b плана `docs/tasks/2026-09-23-stage1-plan.md`. Запускается
после 8a (`docs/tasks/2026-09-24-ledger-orm-models.md`): таблицы `users`,
`accounts`, `categories`, `transactions` уже созданы миграциями.

Решения приняты диспетчером и записаны на `e203cb6` в раздел 4.5: RLS на
всех четырёх таблицах, включая `users` с политикой `p_users_self`; поиск
по `telegram_id` — только через функцию `find_user_by_telegram_id` с
`SECURITY DEFINER`; три роли `finplan`, `finplan_app` и `finplan_worker`;
роли создаёт окружение, миграция только выдаёт права; новая переменная
`MIGRATIONS_DATABASE_URL`.

Сейчас всё подключается под суперпользователем `finplan`, который RLS
обходит. Интеграционные тесты поднимают PostgreSQL через testcontainers в
`tests/conftest.py` (фикстуры `postgres_container`, `database_url`,
`run_alembic`, `fresh_database_url`), а не через docker-compose.

До первой правки прочитать:

- `docs/architecture-brief.md`;
- `docs/architecture.md` через `Read` с `offset` и `limit` по карте из
  выжимки: 4.5 целиком, из 10.1 — строки таблицы с `DATABASE_URL`,
  `WORKER_DATABASE_URL`, `MIGRATIONS_DATABASE_URL`;
- `src/finplan/config.py`, класс `DatabaseSettings`;
- `migrations/env.py`;
- `docker-compose.yml`, `.env.example`;
- `tests/conftest.py`, строки 50–200.

## Задание

1. **Конфигурация.** В `DatabaseSettings` — поле `migrations_url` из
   `MIGRATIONS_DATABASE_URL` с умолчанием `DATABASE_URL` и метод
   `migrations_dsn()` по образцу `worker_url` и `worker_dsn()`.
   `migrations/env.py` подключается через `migrations_dsn()`.
   `.env.example`: `DATABASE_URL` — под `finplan_app`,
   `WORKER_DATABASE_URL` — под `finplan_worker`,
   `MIGRATIONS_DATABASE_URL` — под `finplan`; комментарии объясняют, зачем
   три роли.
2. **Роли в docker-compose.** Скрипт инициализации, создающий
   `finplan_app` (`LOGIN NOBYPASSRLS`) и `finplan_worker`
   (`LOGIN BYPASSRLS`) с паролями, равными именам, — через `configs` с
   `content` в `docker-compose.yml`, смонтированный в
   `/docker-entrypoint-initdb.d/`. Новых каталогов и файлов вне дерева 2.1
   не заводить. Комментарий рядом говорит, что после появления скрипта
   локальный том пересоздаётся командой `docker compose down -v`.
3. **Миграция поверх 8a.** В `upgrade`:
   - проверка, что роли `finplan_app` и `finplan_worker` существуют;
     если нет — исключение с понятным текстом;
   - `GRANT` на существующие таблицы и последовательности и
     `ALTER DEFAULT PRIVILEGES` на будущие — по таблице ролей из 4.5;
   - `ENABLE ROW LEVEL SECURITY` и политика по `user_id` для `accounts`,
     `categories`, `transactions` по образцу 4.5; `p_users_self` для
     `users` дословно по 4.5. `FORCE ROW LEVEL SECURITY` не включать;
   - функция `find_user_by_telegram_id` дословно по 4.5, с `REVOKE` от
     `PUBLIC` и `GRANT EXECUTE` для `finplan_app`.

   `downgrade` снимает всё это в обратном порядке и оставляет таблицы.
   Справочники `currencies` и `exchange_rates` RLS не получают — только
   `SELECT` для обеих ролей.
4. **Тестовая инфраструктура.** Фикстуры в `tests/conftest.py` создают в
   контейнере роли `finplan_app` и `finplan_worker` до миграций,
   запускают Alembic под владельцем и отдают тестам отдельный URL под
   `finplan_app`. Имена существующих фикстур сохранить, чтобы не
   переписывать тесты.
5. **Проверка изоляции на уровне миграции.** В
   `tests/integration/test_migrations.py` — тесты, что:
   - под `finplan_app` без `app.user_id` прямой `SELECT` из `users` пуст,
     а `find_user_by_telegram_id` находит вставленного владельцем
     пользователя;
   - под `finplan_app` с `SET LOCAL app.user_id` на пользователя A не
     видно строк `accounts` пользователя B.

## Границы

- `src/finplan/domain/` и `src/finplan/application/` не изменяются.
- Репозитории и Unit of Work не пишутся — это подзадача 9a. Где
  репозиторий будет вызывать функцию поиска, решает 9a.
- Модели и миграция 8a не переписываются. Всё новое — отдельной
  миграцией.
- `docs/architecture.md` не правится. Если решение из 4.5 не реализуется
  как записано — например, `configs.content` не поддерживается
  установленным docker compose, — вопрос диспетчеру, а не обход.
- Тесты кроме названных в пункте 5 не пишутся — остальные покрывает
  подзадача 10.

## Критерий приёмки

- после `docker compose down -v` проходят `make up` и `make migrate`;
- `uv run alembic downgrade -1`, затем `uv run alembic upgrade head`
  проходят;
- `tests/integration/test_migrations.py` зелёный, включая тесты пункта 5;
- `make test` и `make lint` зелёные;
- `grep -rn "FORCE ROW LEVEL" migrations` пуст.
