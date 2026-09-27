# Диалог дохода

- **Исполнитель:** developer
- **Слой:** entrypoints, `src/finplan/entrypoints/bot/`
- **Раздел архитектуры:** docs/architecture.md, разделы 6.2, 6.3, 6.6,
  6.7
- **Этап:** 1, подзадача 13b из `docs/tasks/2026-09-23-stage1-plan.md`
- **Заведена:** 2026-09-25

## Входные условия

Подзадача 13a закрыта: в `bot/keyboards/ids.py` лежат короткие
идентификаторы, в `bot/keyboards/ledger.py` — клавиатуры выбора
категории, счёта и подтверждения. Функции шагов, параметризованные
`DialogScope` — видом операции, группой состояний и фабрикой
`callback_data`, — лежат в `bot/routers/expense.py` рядом с
хендлерами расхода и `EXPENSE_SCOPE`. Что именно и под какими именами сделано,
описано в разделе «Результат исполнителя» файла
`docs/tasks/done/2026-09-25-bot-expense-dialog.md`. В `bot/states.py` у
`AddIncome` уже есть состояние `comment`. Роутер `income` существует
пустым и подключён в `bot/main.py`.

До первой правки прочитать:

- результат исполнителя в файле задачи 13a;
- `docs/architecture-brief.md`, затем в 6.3 абзацы «Диалог дохода» и
  «Что из диаграммы откладывается на этапе 1» — по номерам строк из
  карты;
- `bot/routers/expense.py`.

Файлы читать нужными кусками, а не целиком.

## Задание

1. **Диалог дохода — `bot/routers/income.py`.** Те же шаги, что у
   расхода: `amount`, `category`, `account`, `confirm`, `comment`.
   Категории вида `income`, группа состояний `AddIncome`, фабрика
   `IncomeCallback`, `kind=TransactionKind.INCOME`. Вход — `/income` и
   кнопка `inc:new`, вход сбрасывает текущее состояние. Шаг
   `recurring` не используется, 6.3, «Что из диаграммы откладывается
   на этапе 1».
2. **Общий модуль шагов.** Первым делом перенести `DialogScope`,
   функции шагов и их вспомогательные функции из `routers/expense.py`
   в новый модуль `bot/routers/ledger_dialog.py` без изменения
   поведения. В `expense.py` остаются `EXPENSE_SCOPE`, `router` и
   хендлеры с фильтрами. Причина: `income.py`, импортирующий из
   `expense.py`, делал бы доход зависимым от модуля расхода. После
   переноса прогнать `make test`.
3. **Без копирования.** Хендлеры `income.py` вызывают функции из
   `ledger_dialog.py` с `INCOME_SCOPE`. Если какая-то функция
   оказалась привязанной к расходу, её разрешено обобщить; поведение
   диалога расхода при этом не меняется.

## Границы

- Изменяются только `bot/routers/income.py`, `bot/routers/expense.py`,
  новый `bot/routers/ledger_dialog.py` и, для обобщения по пункту 3,
  `bot/keyboards/ledger.py`.
- `bot/main.py`, `bot/states.py`, `container.py`, слои `domain`,
  `application`, `infrastructure` и `docs/` не изменяются.
- Новые тесты не пишутся, это подзадача 15b.
- Новые зависимости не добавляются.

## Критерий приёмки

- `make lint` и `make test` зелёные.
- `git diff --stat` не показывает файлов вне перечисленных в границах.
- Скрипт в scratchpad собирает диспетчер через `build_container` и
  `create_dispatcher` на `MemoryStorage` и проверяет, что `income.router`
  содержит обработчики сообщений и нажатий кнопок. Вывод привести в
  результате.

## Объём

Ориентир — около сорока обращений к инструментам. Если к
шестидесятому обращению работа не готова, остановиться, описать в
результате, что сделано и что осталось, и вернуть управление.

## Результат исполнителя

**Сделано.** `DialogScope`, обе структурные протокольные аннотации
(`_LedgerCallbackData`, `_DialogStates`), все текстовые константы шагов
и функции шагов (`enter_dialog`, `handle_amount`,
`_show_category_step`, `handle_category_action`, `_finalize_category`,
`_show_account_step`, `handle_account_action`, `_show_confirm_step`,
`handle_comment`, `handle_confirm_action`, `_external_key`,
`_save_transaction`, `_list_categories`, `_list_accounts`) перенесены
без изменения поведения из `routers/expense.py` в новый
`routers/ledger_dialog.py`; модуль не заводит `Router`, только шаги.
`routers/expense.py` сократился до `EXPENSE_SCOPE` (собран из
`AddExpense`/`ExpenseCallback`/`TransactionKind.EXPENSE`/
`CategoryKind.EXPENSE`), `router` и семи тонких хендлеров с фильтрами,
каждый вызывает соответствующую функцию `ledger_dialog.py` с
`EXPENSE_SCOPE`. `routers/income.py` реализован по тому же образцу:
`INCOME_SCOPE` собран из `AddIncome`/`IncomeCallback`/
`TransactionKind.INCOME`/`CategoryKind.INCOME`, семь хендлеров —
`Command('income')`, `IncomeCallback.filter(F.action == "new")` для
`inc:new`, и по фильтру `StateFilter` на каждое из состояний
`AddIncome.amount/category/account/comment/confirm`. Вход `/income` и
`inc:new` сбрасывают состояние тем же `enter_dialog`, что и расход. Шаг
`recurring` не используется — ни один хендлер не ссылается на
`AddIncome.recurring`, диалог доходит от `account` сразу к `confirm`,
как и требует раздел 6.3, «Что из диаграммы откладывается на этапе 1».
`keyboards/ledger.py` не менялся: обе клавиатуры уже принимали фабрику
`callback_data` параметром (`LedgerCallbackFactory`) после подзадачи
13a, обобщать было нечего.

**Проверка.** `make lint` — зелёный (`build-brief.py --check`, `ruff
check`, `ruff format --check`, `mypy src`: 114 файлов без ошибок).
`make test` — зелёный, `219 passed` (набор тестов не менялся, подзадача
15b добавит тесты диалога дохода). `git diff --stat` после работы
показывает только `routers/expense.py` (458 строк убрано) и
`routers/income.py` (100 строк добавлено); `routers/ledger_dialog.py` —
новый файл, весь список укладывается в границы задачи.

Скрипт `check_income_dialog.py` (в scratchpad, не в репозитории) строит
`Settings()` с тем же минимальным набором переменных, что
`tests/conftest.py::_BASELINE_ENV`, собирает `Container` через
`build_container` и `Dispatcher` через `create_dispatcher` на
`MemoryStorage`, затем проверяет, что `income.router` содержит
обработчики сообщений и нажатий кнопок, включая все семь ожидаемых
хендлеров по имени функции. Вывод:

```
OK: create_dispatcher(build_container(Settings()), MemoryStorage()) собрался
OK: income.router содержит 3 обработчиков сообщений
OK: income.router содержит 4 обработчиков нажатий кнопок
OK: найдены все ожидаемые хендлеры: ['handle_income_account', 'handle_income_amount', 'handle_income_category', 'handle_income_command', 'handle_income_comment', 'handle_income_confirm', 'handle_income_new']
Все проверки пройдены
```

**Решения и отложенное.**

- Перенос в `ledger_dialog.py` — дословный (импорты, тела функций,
  docstring-и шагов не менялись), обновлён только модульный docstring:
  он описывает новое расположение и то, что модуль не содержит
  `Router`, а `expense.py`/`income.py` регистрируют хендлеры со своими
  фильтрами.
- Порядок State в `AddIncome` (`amount, category, account, comment,
  recurring, confirm` — раздел 6.3, дословно скопирован в `states.py`
  подзадачей 13a) не создаёт проблем: `State()` — независимые объекты
  без связи с порядком объявления, диалог просто не ссылается на
  `AddIncome.recurring` ни в одном хендлере или `_show_*`-функции.
- Порядок фильтров в декораторах `income.py` (`IncomeCallback.filter(),
  StateFilter(AddIncome.category)`) сохранён таким же, как в
  `expense.py`, — для единообразия чтения, поведение aiogram от
  порядка фильтров в списке аргументов декоратора не зависит.

**Вопросы диспетчеру.** Пусто.
