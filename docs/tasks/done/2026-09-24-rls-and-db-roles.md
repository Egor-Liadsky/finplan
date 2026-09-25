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

Два ограничения окружения, найденные в 8a (коммит `1cfe287`). Первое:
`make migrate` на хосте не резолвит хост `postgres` из `.env`. Второе:
пересборка сервиса `migrate` падает на `docker-credential-desktop`. Оба
ограничения к коду не относятся. Приёмку `make migrate` исполнитель
проверяет эквивалентом `uv run alembic upgrade head` с URL на
`localhost:5432` и называет замену в результате. `.env` не правится.

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

## Результат исполнителя

**Сделано.** `DatabaseSettings` получил поле `migrations_url`
(`MIGRATIONS_DATABASE_URL`, по умолчанию — `DATABASE_URL`) и метод
`migrations_dsn()` по образцу `worker_url`/`worker_dsn()`; `migrations/env.py`
в обоих режимах (`offline`/`online`) подключается через `migrations_dsn()`, а
не через основной `dsn()`, — после этой миграции у роли `finplan_app` больше
нет прав на DDL. `.env.example` переведён на три роли: `DATABASE_URL` —
`finplan_app`, `WORKER_DATABASE_URL` — `finplan_worker`,
`MIGRATIONS_DATABASE_URL` — `finplan` (владелец схемы), с комментарием,
зачем три роли. `docker-compose.yml`: сервис `postgres` получил `configs` с
`content` — DO-блоком, который создаёт роли `finplan_app` (`LOGIN
NOBYPASSRLS`) и `finplan_worker` (`LOGIN BYPASSRLS`) с паролями, равными
именам ролей, монтируется в `/docker-entrypoint-initdb.d/`; рядом —
комментарий про пересоздание тома `docker compose down -v` и про экранирование
`$$` → `$$$$` (без этого docker compose схлопывает `$$` в `$` при подстановке
переменных, и PostgreSQL падает на `DO $ ... $` с ошибкой синтаксиса — поймано
и исправлено на реальном контейнере).

Миграция `d6cb2637f739` (`grant privileges and enable row level security`,
поверх `2058c667ebfe`): сначала DO-блок проверяет существование ролей
`finplan_app`/`finplan_worker` и падает с понятным `RAISE EXCEPTION`, если
роли нет; затем `GRANT SELECT, INSERT, UPDATE, DELETE` на `users`, `accounts`,
`categories`, `transactions` и `GRANT SELECT` (только чтение) на `currencies`
для обеих ролей, `GRANT USAGE` на последовательности (в схеме их пока нет —
оператор не падает и на пустом множестве), `ALTER DEFAULT PRIVILEGES` без
`FOR ROLE` (действует для роли, что выполняет саму команду, то есть для
владельца схемы под миграциями, — портируемо между `finplan` в
docs/architecture.md и учётной записью `testcontainers` в тестах) на будущие
таблицы и последовательности. Дальше — `ENABLE ROW LEVEL SECURITY` и политика
по `user_id` (`p_accounts_owner`, `p_categories_owner`, `p_transactions_owner`)
для `accounts`/`categories`/`transactions` по образцу `p_transactions_owner`
из 4.5, и `p_users_self` для `users` дословно, с явным `WITH CHECK`. `FORCE
ROW LEVEL SECURITY` нигде не включён. В конце — функция
`find_user_by_telegram_id` дословно по 4.5 (`SECURITY DEFINER`, `SET
search_path = public, pg_temp`), `REVOKE ALL ... FROM PUBLIC` и `GRANT EXECUTE`
только для `finplan_app` (по тексту задания подзадачи, не для `finplan_worker`
— хотя роль по общей таблице 4.5 имеет «те же права», для этой функции 4.5 в
явном SQL-примере называет только `finplan_app`). `downgrade` снимает всё в
обратном порядке и оставляет таблицы: `REVOKE EXECUTE`, `DROP FUNCTION`,
`DROP POLICY` + `DISABLE ROW LEVEL SECURITY` по всем четырём таблицам,
`ALTER DEFAULT PRIVILEGES ... REVOKE`, затем прямые `REVOKE` на объекты.

`tests/conftest.py`: `postgres_container` сразу после старта контейнера
однократно создаёt роли `finplan_app`/`finplan_worker` через новую функцию
`_create_database_roles` (роли кластерные — видны любой базе внутри
контейнера, включая создаваемые `fresh_database_url`), поэтому цикл миграций
в `test_migrations.py` и любые будущие тесты с `fresh_database_url` не падают
на проверке ролей в новой миграции. Новая фикстура `app_database_url`
(function-scope, зависит от `migrated_database`) отдаёт тестам URL той же
базы под ролью `finplan_app` — через `_with_role`, который подменяет только
логин/пароль в строке подключения. Имена и поведение существующих фикстур
(`postgres_container`, `database_url`, `migrated_database`, `run_alembic`,
`fresh_database_url`, `env_vars`, `db_session`) не менялись, только
`migrated_database`/`postgres_container` получили уточняющие докстринги.

`tests/integration/test_migrations.py`: класс `TestRowLevelSecurityUnderAppRole`
с двумя тестами пункта 5 задания — `test_users_direct_select_empty_but_find_by_telegram_id_works`
(владелец вставляет пользователя, под `finplan_app` без `app.user_id` прямой
`SELECT` из `users` даёт 0 строк, `find_user_by_telegram_id` находит того же
пользователя) и `test_app_user_id_hides_other_users_accounts` (два владельца
со своими счетами; под `finplan_app` с `SELECT set_config('app.user_id',
:id, true)` — эквивалент параметризуемого `SET LOCAL`, сам `SET LOCAL`
bind-параметры не принимает — на пользователя A виден только его счёт, не
счёт B).

**Проверка.**
- `uv run pytest -q` → `158 passed` (было 151, добавилось 2 новых теста в
  `test_migrations.py`; часть прироста — уже существовавшие тесты других
  подзадач, шедшие параллельно в git-истории).
- `make test` → `158 passed`.
- `make lint` → зелёный (`docs/build-brief.py --check`, `ruff check`,
  `ruff format --check`, `mypy src` — все прошли).
- `grep -rn "FORCE ROW LEVEL" migrations` → пусто (код возврата 1).
- Ручной прогон вместо `make migrate` (замена по задаче — хост не резолвит
  `postgres` из `.env`, `.env` не правился): `docker compose down -v`, затем
  `make up` (postgres поднялся с ролями через `configs`, все сервисы
  стартовали на закешированных образах, `migrate` внутри контейнера применил
  только первую миграцию — образ собран до этой подзадачи, пересборка
  `docker compose build migrate` подтверждённо падает на
  `docker-credential-desktop`, это известное ограничение окружения, не кода),
  затем `DATABASE_URL=postgresql+asyncpg://finplan:finplan@localhost:5432/finplan
  uv run alembic upgrade head` — довёл схему до `head`; `curl
  http://localhost:8000/health` вернул `{"status":"ok","...,"database":{"ok":true}}`.
  Циклы `uv run alembic downgrade -1` → `upgrade head` и `upgrade head` →
  `downgrade base` → `upgrade head` (на testcontainers, тест
  `test_migration_cycle_upgrade_downgrade_upgrade`, и вручную на локальном
  контейнере) прошли без ошибок.
- Дополнительно вручную (не автоматизированный тест, для собственной
  уверенности перед автоматизацией пункта 5): под `finplan_app` создание
  строки в `pg_policies` подтвердило `qual`/`with_check` для всех четырёх
  политик, `pg_class.relacl`/`relrowsecurity` — гранты и статус RLS на
  `accounts`/`categories`/`transactions`/`currencies`, `pg_proc.proacl` —
  права на функцию только для `finplan`/`finplan_app`.

**Решения и отложенное.**
- `ALTER DEFAULT PRIVILEGES` написан без `FOR ROLE finplan`: с явным именем
  роли миграция падала в тестах — роль-владелец в контейнере
  `testcontainers` называется не `finplan` (её создаёт сам testcontainers).
  Без `FOR ROLE` команда по документации PostgreSQL действует для роли,
  которая её выполняет, то есть для той же роли, что видна в
  `MIGRATIONS_DATABASE_URL`/`migrations_dsn()` в любом окружении — это не
  расхождение с 4.5 (там имя роли `finplan` не упомянуто рядом с
  `ALTER DEFAULT PRIVILEGES`), а более портируемая формулировка того же
  правила.
- `$$` в `content` докер-конфига экранирован как `$$$$` — без этого
  docker compose схлопывает его в один `$` при подстановке переменных
  окружения, и PostgreSQL получает синтаксически неверный `DO $ ... $`.
  Найдено и исправлено по факту падения `postgres` при первом `make up`.
- `ALTER DEFAULT PRIVILEGES ... ON TABLES` для будущих объектов даёт полный
  CRUD, без исключения для будущих справочников вроде `exchange_rates`:
  на момент этой миграции такой таблицы ещё нет (создаёт её будущая
  подзадача), а `ALTER DEFAULT PRIVILEGES` не умеет различать таблицы по
  имени. Когда `exchange_rates` появится, её миграции придётся сузить права
  явным `GRANT SELECT` — тем же приёмом, каким `currencies` сужен в этой
  миграции. Названо в комментарии рядом с кодом, решением диспетчера не
  считаю — то же правило 4.5, применённое по факту создания таблицы, а не
  заранее.
- Тестовый скрипт `_create_database_roles` создаёт роли DO-блоком с проверкой
  `IF NOT EXISTS` (идемпотентно), а не `CREATE ROLE IF NOT EXISTS` — в
  PostgreSQL такого синтаксиса нет.
- Локальный `.env` (не `.env.example`) не правился по прямому указанию в
  задаче: `DATABASE_URL` в нём по-прежнему указывает на роль `finplan`
  (владельца), не на `finplan_app`. Функционально это не ломает `api`/`bot` —
  владелец RLS обходит, — но и не демонстрирует локально изоляцию под
  `finplan_app`, которую даёт эта подзадача. Перенос значений из
  `.env.example` в `.env` — на усмотрение диспетчера (это его файл, не
  правил).
- После проверки контейнеры `docker compose` оставлены запущенными
  (`postgres`, `redis`, `api`, `bot`, `worker`), база — на актуальной
  ревизии `d6cb2637f739`; тестовые строки, вставленные вручную при проверке
  RLS, удалены (`DELETE FROM accounts; DELETE FROM users;`).
- Репозитории и Unit of Work не создавались (граница задания, подзадача 9a);
  использование `find_user_by_telegram_id` из репозитория — тоже её решение.

**Вопросы диспетчеру.**

Нет.
