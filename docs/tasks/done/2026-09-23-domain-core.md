# Доменное ядро этапа 1: деньги, валюта, период, сущности

- **Исполнитель:** developer
- **Слой:** domain
- **Раздел архитектуры:** docs/architecture.md, разделы 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 4.2
- **Заведена:** 2026-09-23

## Входные условия

Каркас этапа 0 готов: пакеты `src/finplan/domain/common/`, `entities/`,
`finance/`, `services/` существуют и пусты, кроме `__init__.py`.
`make test` и `make lint` зелёные, включая `tests/unit/test_layering.py`.

Это подзадача 1 плана `docs/tasks/2026-09-23-stage1-plan.md`. Диспетчер уже
дополнил документ правилами, на которые опирается задание: дефолтный набор
категорий и правило слагов в `path`, форма сторно, место перечислений,
допустимость знака у `Money`.

До первой правки прочитать:

- `docs/architecture-brief.md` целиком — там дословно разделы 2.2 и 3.1;
- `docs/architecture.md` по номерам строк через `Read` с `offset` и `limit`:
  дерево `domain/` в разделе 2.1 — строки 235–263; раздел 3.2 — 444–466;
  раздел 3.3: `User` 469–490, `Account` 491–519, `Category` 533–590,
  `Transaction` 591–645; раздел 3.4 — 745–785; раздел 4.2 — 809–833.

## Задание

Реализовать доменное ядро, нужное этапу 1, чистым Python 3.12 без IO.

`domain/common/`:

- `currency.py` — value object `Currency`: код ISO 4217 из трёх заглавных
  латинских букв и `minor_unit` от 0 до 4; неизменяемый и сравнимый по
  значению. Модульные константы `RUB`, `USD`, `EUR` с `minor_unit = 2`.
- `money.py` — value object `Money(amount: Decimal, currency: Currency)` по
  разделу 3.1: единый `decimal.Context` с `ROUND_HALF_UP`, объявленный в этом
  модуле и используемый явно; сложение и вычитание только в одной валюте,
  иначе `CurrencyMismatchError`; умножение только на `Decimal` или `int`;
  деление возвращает `Decimal`; округление до `minor_unit` валюты отдельным
  методом; нулевое значение валюты. Знак `Money` допускает (раздел 3.1,
  последний абзац о знаке). `amount` принимается только типа `Decimal`,
  любой другой тип отклоняется `TypeError` проверкой «не `Decimal`», без
  перечисления запрещённых типов.
- `period.py` — value object `Period` для полуинтервала дат `[start, end)`,
  `start < end`; проверка принадлежности даты; конструкторы дня и
  календарного месяца.
- `errors.py` — базовое доменное исключение и производные, нужные этой
  задаче: несовпадение валют, нарушение инварианта сущности, запрет
  повторного сторно.

`domain/entities/` — `user.py`, `account.py`, `category.py`,
`transaction.py` с атрибутами и инвариантами из таблиц раздела 3.3. Сущности
неизменяемы; изменение состояния возвращает новый объект. Перечисления
`AccountType`, `TransactionKind`, `TransactionStatus`, `CategoryKind` —
`enum.StrEnum` в модулях своих сущностей, как описано в конце раздела 3.2.
Остальные перечисления из 3.2 и сущности `Budget`, `SavingsGoal`, `Deposit`,
`RecurringRule`, `AccountValuation` в эту задачу не входят.

- `Transaction`: сумма строго больше нуля; форма `transfer` и обязательность
  `category_id` — по инвариантам 3.3 и ограничениям `ck_transactions_*`;
  комментарий до 500 символов; ограничение на будущий `occurred_at` для
  `posted` проверяется с `now`, переданным аргументом (у домена нет часов).
  Сторно — метод исходной операции по правилу «Форма сторно» в 3.3: он
  возвращает пару из исходной в `reversed` и сторнирующей записи, а для
  операции не в `posted` поднимает доменную ошибку. Идентификатор и
  `created_at` сторнирующей записи приходят аргументами.
- `Category`: слаг по регулярному выражению из 3.3, `path` и `depth` из
  родителя, `depth` не больше 2, `kind` совпадает с родительским.
- Дефолтный набор категорий — константа `DEFAULT_CATEGORY_TREE` в
  `category.py` по таблице «Дефолтный набор» в 3.3, данными, а не
  сущностями, плюс чистая функция, строящая из неё список `Category` для
  заданного `user_id` с идентификаторами от переданной фабрики. Порядок в
  таблице задаёт `sort_order`.
- `Account`: остаток не хранится как поле (раздел 3.3); валюта
  `opening_balance` совпадает с валютой счёта.

Идентификаторы — `uuid.UUID`, генерацию UUIDv7 домен не выполняет:
идентификатор приходит аргументом.

Тесты домена в эту задачу не входят — их пишет `tester` в подзадаче 2.
Существующие проверки держать зелёными.

## Границы

- изменения только внутри `src/finplan/domain/`: `git diff --stat` не
  содержит других путей;
- новые файлы только из дерева `domain/` раздела 2.1; `daycount.py`,
  `finance/` и `services/` не заполняются;
- в `src/finplan/domain/` нет импортов `application`, `infrastructure`,
  `entrypoints`, `sqlalchemy`, `aiogram`, `fastapi`, `pydantic`;
- слово `float` в `src/finplan/domain/` не встречается нигде, включая
  проверки типа и комментарии;
- `pyproject.toml` и `uv.lock` не изменяются;
- `docs/`, `tests/` и `CLAUDE.md` не изменяются, кроме раздела «Результат
  исполнителя» в этом файле задачи;
- общие границы этапа 1: нет курсов валют, Redis, HTTP-эндпоинтов для SPA и
  `frontend/`; FSM — `MemoryStorage`; проведённые операции не изменяются и
  не удаляются, отмена — только сторно (раздел 4.2); каталоги вне дерева
  раздела 2.1 не создаются.

## Критерий приёмки

Дословно из плана этапа: файлы существуют; `grep -rn "float"
src/finplan/domain` пуст; `make test` и `make lint` зелёные;
`git diff --stat` не выходит за `src/finplan/domain/`.

Существуют `domain/common/money.py`, `currency.py`, `period.py`,
`errors.py` и `domain/entities/user.py`, `account.py`, `category.py`,
`transaction.py`; в `category.py` есть `DEFAULT_CATEGORY_TREE`, в
`transaction.py` — метод сторно.

## Результат исполнителя

**Сделано.** Реализовано доменное ядро этапа 1 чистым Python без IO.

- `domain/common/currency.py` — неизменяемый `Currency` (frozen dataclass,
  сравнение по значению), код проверяется regex `^[A-Z]{3}$`, `minor_unit` —
  диапазоном 0–4; константы `RUB`, `USD`, `EUR` с `minor_unit = 2`.
- `domain/common/money.py` — `Money(amount: Decimal, currency: Currency)`.
  Контекст округления `MONEY_ROUNDING_CONTEXT = Context(prec=28,
  rounding=ROUND_HALF_UP)` объявлен и применяется явно только в
  `round_to_minor_unit()` (квантование до `10^-minor_unit` через
  `Decimal.scaleb`), остальная арифметика — обычный `Decimal` без округления.
  `+`/`-` требуют одной валюты (`CurrencyMismatchError` иначе), `*` — только
  на `Decimal`/`int` (исключая `bool`), `/` всегда возвращает `Decimal` (при
  делении на `Money` — как безразмерное отношение, при делении на
  `Decimal`/`int` — как пропорциональная величина). `amount` в
  `__post_init__` проверяется единственной проверкой `isinstance(amount,
  Decimal)`, без перечисления запрещённых типов. Знак `Money` не
  ограничивается — как явно разрешено разделом 3.1.
- `domain/common/period.py` — `Period(start, end)` с инвариантом `start <
  end`, метод `contains`, конструкторы `for_day` и `for_month` (с переходом
  через декабрь без внешних библиотек).
- `domain/common/errors.py` — `DomainError` и три потомка:
  `CurrencyMismatchError`, `InvariantViolationError` (общий инвариант
  сущности/value object — использован и в `Currency`, и в `Period`, и во
  всех сущностях, отдельного класса под каждую сущность не заводил),
  `AlreadyReversedError` (повторное сторно).
- `domain/entities/user.py` — `User` с дефолтами `base_currency = RUB`,
  `timezone = "Europe/Moscow"`, `locale = "ru"`, `is_active = True`; без
  дополнительных инвариантов сверх типов — раздел 3.3 их не описывает.
- `domain/entities/account.py` — `AccountType(StrEnum)` по разделу 3.2,
  `Account` без поля остатка (он производный, раздел 3.3); единственный
  runtime-инвариант — валюта `opening_balance` совпадает с валютой счёта.
- `domain/entities/category.py` — `CategoryKind(StrEnum)`, `Category` с
  проверкой слага `^[a-z][a-z0-9_]*$` для каждого сегмента `path`,
  соответствия `depth` числу сегментов, `depth` от 0 до 2, согласованности
  `parent_id` с `depth`. Фабрики `Category.new_root` и `Category.new_child`
  берут `path`, `depth` и `kind` у родителя, поэтому нарушить «kind
  совпадает с родительским» через них невозможно структурно (прямой вызов
  конструктора с чужим `kind` этот кросс-инвариант не проверяет — у сущности
  нет ссылки на объект-родителя, только `parent_id`; проверяется только
  через фабрику). Данные `DEFAULT_CATEGORY_TREE` — кортеж
  `DefaultCategoryRoot`/`DefaultCategoryChild` (не сущности) по таблице
  «Дефолтный набор»; чистая функция `build_default_categories(user_id,
  id_factory)` строит из них список `Category`. `sort_order` — сквозной
  счётчик по порядку строк таблицы (корень, затем сразу его потомки, затем
  следующий корень) — не перезапускается для каждого уровня.
- `domain/entities/transaction.py` — `TransactionKind`, `TransactionStatus`
  (`StrEnum`, раздел 3.2), `Transaction` с полями ровно по таблице раздела
  3.3 (без `transfer_group_id`, `currency`, `occurred_on` — это колонки
  таблицы БД, обслуживающие персистентность, а не атрибуты сущности из 3.3).
  `__post_init__` проверяет сумму `> 0`, длину комментария, форму `transfer`
  (`counter_account_id` обязателен и `!= account_id`, `category_id`
  запрещён) и обязательность `category_id` для `income`/`expense`.
  Ограничение на будущий `occurred_at` для `posted` вынесено в отдельный
  классовый метод `Transaction.new(..., now=...)`, а не в `__post_init__`:
  инвариант зависит от текущего момента, которого у домена нет, а обычный
  конструктор (`Transaction(...)`) нужен ещё и для восстановления уже
  проверенных операций из хранилища, где второй раз сверяться с `now` не
  нужно. Метод `reverse(reversal_id, created_at)` возвращает пару
  `(исходная в reversed, сторнирующая запись)`, для не-`posted` поднимает
  `AlreadyReversedError`. Все поля сторнирующей записи скопированы из
  исходной через `dataclasses.replace`, кроме `id`, `status`, `created_at`,
  `reverses_id`; отдельно решил не копировать `external_key` (обнулил) —
  задание перечисляет только `id` и `created_at` как аргументы метода и не
  called-out `external_key` среди копируемых полей, а копирование сломало
  бы `uq_transactions_user_id_external_key` (раздел 4.3): исходная запись
  остаётся в таблице с тем же `external_key`, что и сторнирующая, если бы
  её скопировали.

**Проверка.** Первый заход проверял вручную только `uv run ruff check .`,
`uv run mypy src`, `uv run pytest -q` — все три были зелёными, но это не
`make lint`: команда не запускалась, и `ruff format --check`, которым она
дополнительно проверяет, пропущен не был назван пропущенным. По замечанию
диспетчера прогнан `make lint` целиком; он упал на `uv run ruff format
--check` — `3 files would be reformatted`, первым — `currency.py:33`.
Файлы отформатированы командой `uv run ruff format src/finplan/domain` (3
files reformatted, 10 files left unchanged; изменились только пробелы —
содержательных изменений не было). После этого повторный `make lint`
прошёл целиком: `build-brief.py --check` — «docs/architecture-brief.md
соответствует docs/architecture.md», `ruff check` — чисто, `ruff format
--check` — «79 files already formatted», `mypy src` — `Success: no issues
found in 61 source files` (для `finplan.domain.*` и
`finplan.application.*` в `pyproject.toml` включён `strict = true`).
`make test` (`uv run pytest`) — `10 passed`, включая оба теста
`tests/unit/test_layering.py`. `grep -rn "float" src/finplan/domain` — пусто.
`git diff --stat` (после `git add -N` только для новых файлов домена, затем
`git reset`, чтобы не оставлять индекс тронутым) — восемь новых файлов
целиком в `src/finplan/domain/common/` и `src/finplan/domain/entities/`;
предсуществующие изменения `docs/architecture-brief.md` и
`docs/architecture.md` в рабочем дереве были там до начала этой задачи (по
снимку git status в начале сессии) и этой задачей не тронуты.

**Решения и отложенное.**

- `InvariantViolationError` сделан одним общим классом на все сущности и
  value objects, а не отдельным классом на сущность — задание просит только
  «нарушение инварианта сущности» как один вид ошибки, а не иерархию по
  сущностям.
- Проверка "kind категории совпадает с родительским" реализована только как
  свойство фабрик `new_root`/`new_child`, а не как runtime-инвариант самого
  `__post_init__` — у `Category` нет ссылки на объект-родителя, только
  `parent_id`, поэтому кросс-объектную проверку негде разместить без похода
  в хранилище (это будет проверяться на уровне `application`/БД при
  реальном создании через репозиторий).
- `sort_order` дефолтного набора выбран сквозным по порядку строк таблицы
  (не отдельным счётчиком на уровень) — самое буквальное прочтение фразы
  «порядок перечисления задаёт `sort_order`».
- Тесты домена в эту подзадачу не входят по заданию — оставлены `tester`
  подзадаче 2 того же плана.

**Вопросы диспетчеру.**

Нет.
