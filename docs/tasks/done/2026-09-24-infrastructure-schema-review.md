# Ревью инфраструктуры этапа 1: ORM-модели, миграции, роли и RLS

- **Исполнитель:** reviewer
- **Слой:** infrastructure
- **Раздел архитектуры:** docs/architecture.md, разделы 2.2, 3.1, 4.1, 4.2, 4.3, 4.5, 10.4
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 11a плана `docs/tasks/2026-09-23-stage1-plan.md`. Подзадача
11 «Ревью инфраструктуры» — ревью `git diff` подзадач 8–10, то есть
диапазона `e3aad34..540d38c`, около 3 650 строк. По объёму она разбита на
четыре задачи, которые запускаются одновременно и результатов друг друга не
читают:

- 11a — схема: ORM-модели, миграции, конфигурация, правки документа
  (`docs/tasks/2026-09-24-infrastructure-schema-review.md`);
- 11b — доступ к данным: репозитории, Unit of Work, RLS, запросы журнала и
  правка `occurred_on` в domain и application
  (`docs/tasks/2026-09-24-infrastructure-data-access-review.md`);
- 11c — фикстуры, тесты миграций, репозиториев и модульные тесты правки
  `occurred_on` (`docs/tasks/2026-09-24-infrastructure-repository-tests-review.md`);
- 11d — тесты запросов журнала и изоляции пользователей
  (`docs/tasks/2026-09-24-infrastructure-isolation-tests-review.md`).

Этот файл — 11a.

Закрытые подзадачи и их отчёты в `docs/tasks/done/`: 8a
`2026-09-24-ledger-orm-models.md`, 8b `2026-09-24-rls-and-db-roles.md`, 9a
`2026-09-24-repositories-uow.md`, 9b `2026-09-24-ledger-queries.md`, 9c
`2026-09-24-transaction-occurred-on-{domain,application,infrastructure}.md`,
10a `2026-09-24-repositories-integration-tests.md`, 10b
`2026-09-24-ledger-queries-isolation-tests.md`. Отчёты читать только при
необходимости понять, почему выбрано так, а не иначе, — предмет ревью код, а
не отчёты.

Предмет ревью — около 720 строк кода и 114 строк правок документа:

```bash
git diff --stat e3aad34..540d38c -- src/finplan/infrastructure/db/models src/finplan/config.py migrations docs/architecture.md
git diff e3aad34..540d38c -- src/finplan/infrastructure/db/models
git diff e3aad34..540d38c -- 'migrations/versions/*create_accounts_categories_transactions.py'
git diff e3aad34..540d38c -- 'migrations/versions/*grant_privileges_and_rls.py' migrations/env.py src/finplan/config.py
git diff e3aad34..540d38c -- docs/architecture.md
```

Дифф читать по частям, как выше, а не одним выводом на весь предмет;
крупный файл миграции — с отсечением через `sed -n`.

До начала ревью прочитать:

- `docs/architecture-brief.md` целиком — карта документа и дословные
  правила слоёв, денег и схемы БД;
- `docs/architecture.md` через `Read` с `offset` и `limit`: 4.1 — строки
  861–881; 4.2 — 882–906; из 4.3 (907–1267) — таблицы `users`, `accounts`,
  `categories`, `transactions`; 4.5 — 1430–1519; 10.4 — 2818–2844. Если
  номера строк разошлись с картой в выжимке, верна карта в выжимке.

## Задание

Проверить дифф по списку «Что искать» из роли `reviewer` с упором на схему
базы:

- модели и миграция совпадают с таблицами раздела 4.3 столбец в столбец:
  типы, `NOT NULL`, значения по умолчанию, `CHECK`, уникальные ключи,
  внешние ключи с их `ON DELETE`, индексы; денежные столбцы —
  `NUMERIC(20, 4)` по 3.1 и 4.1, нигде не `float` и не `Float`;
- соглашения 4.1 выполнены: имена ограничений и индексов, `timestamptz`,
  первичные ключи, `user_id` в каждой таблице пользовательских данных;
- неизменяемость журнала по 4.2 поддержана схемой в той мере, в какой
  документ этого требует (права роли приложения на `UPDATE` и `DELETE`
  `transactions`, ограничение на `reverses_id`);
- роли, привилегии, политики RLS и функция поиска пользователя до
  аутентификации соответствуют 4.5: `FORCE ROW LEVEL SECURITY` там, где
  требуется, политики на все таблицы пользовательских данных, функция
  `SECURITY DEFINER` с зафиксированным `search_path` и минимальным
  результатом, роль приложения не владеет таблицами;
- `downgrade` обеих миграций обратим и не оставляет ролей, функций и
  политик, мешающих повторному `upgrade head`;
- `migrations/env.py` и `config.py` не нарушают 10.4 и не смешивают
  подключение владельца схемы для миграций с подключением приложения;
- правки документа в этом диапазоне (3.3, 4.3, 4.5 и хвост в разделе 8)
  согласованы с кодом и с остальным документом.

Известное и уже учтённое находкой не повторять:

- представление кросс-валютного перевода парой строк не определено и
  записано открытым вопросом в 3.3; решается на этапе 2;
- локальный `.env` разработчика подключается под владельцем схемы — это
  окружение, а не код;
- `make lint` не проверяет `mypy` каталог `tests/`.

Каждую находку отнести к одному из уровней:

- **нарушение** — противоречит `docs/architecture.md` или правилу слоёв,
  блокирует отметку подзадачи 11;
- **замечание** — поведение корректно по документу, но есть реальный риск
  дефекта на следующих подзадачах этапа 1 (12a–16, entrypoints и сквозные
  тесты); назвать, на какой подзадаче плана он проявится;
- **к документу** — код прав, а документ устарел или молчит; адресуется
  диспетчеру для правки документа.

## Границы

- правится только раздел `## Результат исполнителя` в этом файле; `src/`,
  `tests/`, `migrations/`, `docs/architecture.md`, `docs/dev-log.md` и
  остальные файлы `docs/` не изменяются — проверяется `git status --short`;
  неотслеживаемый каталог `.claude/skills/jev-skill-suggestion/` к задаче не
  относится;
- тесты и линтеры не запускаются: на `540d38c` `uv run pytest -q` даёт
  210 passed, `make lint` зелёный, это проверено диспетчером; если находке
  нужен прогон, так и написать;
- ревью не выходит за файлы из первой команды `git diff --stat` выше; репозитории, Unit of Work, запросы и тесты — предмет задач 11b–11d, находки по ним здесь не пишутся;
- вкусовщина без ссылки на правило документа в список не попадает.

## Критерий приёмки

- в конце файла есть раздел `## Результат исполнителя` из четырёх подпунктов
  по `docs/tasks/README.md`;
- каждая находка содержит `file:line`, существующий в `540d38c`, уровень из
  трёх названных, нарушенное правило с номером раздела документа и
  последствие;
- если находок какого-либо уровня нет, это сказано прямым текстом;
- `git status --short` показывает изменёнными только файлы задач 11a–11d.

## Результат исполнителя

**Сделано.** Отревьюены ORM-модели `accounts.py`, `categories.py`,
`transactions.py`, `models/__init__.py`, обе миграции подзадач 8a/8b
(`2058c667ebfe_create_accounts_categories_transactions.py`,
`d6cb2637f739_grant_privileges_and_rls.py`), `migrations/env.py`,
`src/finplan/config.py` и правки `docs/architecture.md` в диапазоне
`e3aad34..540d38c` — все файлы из команды `git diff --stat` задания.
Найдена 1 находка уровня **нарушение**, находок уровней «замечание» и
«к документу» нет.

**Проверка.**

- **нарушение** — `migrations/versions/20260924_1500-2058c667ebfe_create_accounts_categories_transactions.py:42`
  (`name="name_length"`), `:43-47` (`name="type_allowed"`), `:83`
  (`name="no_self_parent"`), `:84` (`name="kind_allowed"`), `:85`
  (`name="depth_range"`), `:139-142` (`name="kind_allowed"`), `:143`
  (`name="status_allowed"`), `:144` (`name="amount_positive"`), `:145`
  (`name="comment_length"`), `:146` (`name="base_rate_positive"`),
  `:147-149` (`name="source_allowed"`), `:150-155`
  (`name="transfer_shape"`), `:156-160` (`name="category_required"`) —
  нарушает соглашение об именах ограничений из раздела 4.1
  (`ck_%(table_name)s_%(constraint_name)s`), причём для трёх из них
  полное имя приведено в самом документе дословно: `ck_categories_no_self_parent`
  (раздел 4.3, строка 1012 текущей редакции — «Ограничения:
  `uq_categories_user_id_path`, `ck_categories_no_self_parent`
  (`id <> parent_id`)»), `ck_transactions_transfer_shape` и
  `ck_transactions_category_required` (раздел 4.3, SQL-блок, строки
  1052–1070). `op.create_table` в Alembic строит `Table` на «голой»
  `sa.MetaData()` без `naming_convention` из
  `finplan.infrastructure.db.base.Base` (проверено рендером DDL через
  `alembic.operations.ops.CreateTableOp.to_table()` — `CheckConstraint`
  получает буквально `name`, без префикса `ck_<table>_`), поэтому
  реальная схема после `upgrade head` содержит ограничения с именами
  `type_allowed`, `name_length`, `no_self_parent`, `kind_allowed`,
  `depth_range`, `amount_positive`, `comment_length`,
  `base_rate_positive`, `source_allowed`, `transfer_shape`,
  `category_required` — без ожидаемого документом префикса. Для
  сравнения: PK, FK, UQ и все индексы в этой же миграции заданы полными
  именами вручную (`fk_accounts_user_id`, `pk_transactions`,
  `uq_transactions_reverses_id`, `ix_transactions_user_id_occurred_at`
  и т. д.) и совпадают с документом — упущены только `CheckConstraint`.
  ORM-модели (`accounts.py:50,52`, `categories.py:39,41,44`,
  `transactions.py:55-71`) сами по себе корректны: та же короткая форма
  `name=` там превращается в полное имя автоматически, потому что
  `Table` строится на `Base.metadata` с `NAMING_CONVENTION` — проверено
  напрямую (`Account.__table__.constraints`, `Category.__table__`,
  `Transaction.__table__` дают `ck_accounts_type_allowed`,
  `ck_categories_no_self_parent`, `ck_transactions_transfer_shape` и
  т. д.). Расхождение — только между `Base.metadata` (используется как
  `target_metadata` для Alembic, согласно докстрингу
  `models/__init__.py`) и тем, что реально создаёт написанная вручную
  миграция. Последствие: реальные имена ограничений в БД не совпадают с
  тем, что ожидает документ и `target_metadata`; любая ручная команда
  или будущая миграция, ссылающаяся на документированное имя (например
  `DROP CONSTRAINT ck_accounts_type_allowed`), упадёт «constraint does
  not exist», а `alembic check`/автогенерация, если когда-нибудь
  включится (докстринг `models/__init__.py` называет это одной из целей
  общей `Base.metadata`), будет видеть постоянный дрейф по каждому
  `CHECK` этих трёх таблиц.
- Находок уровня «замечание» нет.
- Находок уровня «к документу» нет: правки `docs/architecture.md` в
  разделах 3.3, 4.3, 4.5 и таблице переменных окружения (10.1)
  согласованы с кодом миграций, моделей и `config.py` — сверено построчно
  с `git diff e3aad34..540d38c -- docs/architecture.md`.
- Остальное по списку «что искать» — без находок: денежные столбцы
  везде `numeric(20,4)`/`numeric(18,10)`, `float` не встречается (проверено
  `grep`); первичные ключи, `timestamptz`, `user_id` в каждой
  пользовательской таблице, `ON DELETE` у FK, частичные и обычные
  индексы совпадают с разделом 4.3 столбец в столбец; роли, привилегии,
  политики RLS, `FORCE` не включён (что и требуется, иначе ломает
  `SECURITY DEFINER`), функция `find_user_by_telegram_id` с фиксированным
  `search_path` и `REVOKE ALL … FROM PUBLIC` — дословно по разделу 4.5;
  `downgrade` обеих миграций симметричен `upgrade` и не оставляет
  политик/функций/ролей, мешающих повторному `upgrade head`;
  `migrations/env.py` и `config.py` подключаются к БД через
  `migrations_dsn()` (роль `finplan`), не смешивая её с `DATABASE_URL`
  приложения — соответствует 10.4 и 4.5. Направление зависимостей и
  импорты в моделях чистые (только SQLAlchemy и `finplan.infrastructure.db.base`).
- Чего не хватает: прогон миграций (`alembic upgrade head` /
  `downgrade`) и интеграционных тестов схемы (`uv run pytest` по
  `tests/integration`) — находка про имена `CheckConstraint` выведена из
  статического рендера DDL (`CreateTable(...).compile(...)`), а не из
  реального применения к PostgreSQL; фактический прогон — работа
  `tester`, и стоит также проверить, не завязаны ли уже написанные тесты
  подзадачи 10a/10c на короткие имена ограничений (тогда их придётся
  поправить вместе с миграцией).

**Решения и отложенное.** Известные и заведомо не находки (открытый
вопрос кросс-валютного перевода в 3.3, локальный `.env` под владельцем
схемы, отсутствие `mypy` для `tests/` в `make lint`) не включены в
список — они уже названы диспетчером как учтённые. Не стал заводить
отдельную находку про `GRANT USAGE ON ALL SEQUENCES IN SCHEMA public`
(в схеме этапа 1 нет ни одной таблицы с `serial`/`bigserial` — все PK
`uuid`, генерируются приложением): это буквально требование раздела 4.5
(«USAGE на последовательности» в таблице ролей), а не самодеятельность
миграции, поэтому не вкусовщина и не нарушение — просто пока не на что
опереться, но код прав по документу.

**Вопросы диспетчеру.** Нет.

## Решение диспетчера

Находка «нарушение» про имена CHECK-ограничений отклонена как ложная.
В работающей базе, поднятой `make migrate`, запрос к `pg_constraint`
показывает полные имена: `ck_accounts_name_length`,
`ck_categories_no_self_parent`, `ck_transactions_transfer_shape`,
`ck_transactions_category_required` и остальные. Alembic в
`op.create_table` строит `MetaData` с `naming_convention` из
`target_metadata`, который `migrations/env.py` берёт из `Base.metadata`;
статический рендер DDL в ревью шёл без контекста миграции, поэтому
показал короткие имена. Правок не требуется.
