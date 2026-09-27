# Парсер быстрого ввода и форматтеры бота

- **Этап:** 1, подзадача 12a из `docs/tasks/2026-09-23-stage1-plan.md`
- **Заведена:** 2026-09-24

## Задание

- **Исполнитель:** `developer`.
- **Слой и раздел архитектуры:** `entrypoints`, только
  `src/finplan/entrypoints/bot/parsers/` и
  `src/finplan/entrypoints/bot/formatters/`. Опора на разделы 6.5
  (грамматика и примеры разбора), 6.6 (валидация, включая абзацы о
  границе между парсером и хендлером и о `parse_mode=HTML`), 3.1
  (деньги, `Decimal`, `ROUND_HALF_UP`) и 2.2 (правила слоёв). Номера строк
  взять из карты в `docs/architecture-brief.md`.
- **Входные условия:** доменный и прикладной слои этапа 1 готовы. До
  первой правки прочитать:
  - `docs/architecture-brief.md`;
  - разделы 6.5 и 6.6 `docs/architecture.md` по номерам строк из карты;
  - `src/finplan/domain/common/currency.py`, `money.py` и `errors.py`;
  - `TransactionKind` в `src/finplan/domain/entities/transaction.py`;
  - `src/finplan/application/errors.py`;
  - `DuplicateError` в `src/finplan/application/ports/repositories.py`;
  - DTO в `src/finplan/application/dto/accounts.py`, `reports.py` и
    `transactions.py`.

  Файлы читать нужными кусками, а не целиком.

### Что сделать

**1. `parsers/quickinput.py`** — разбор строки по грамматике 6.5:
`[знак] сумма [валюта] [текст] [#категория] [@счёт] [!дата]`.

- Публичная функция `parse_quick_input(text: str, *, today: date) -> QuickInput`.
  `today` — сегодняшняя дата в таймзоне пользователя; парсер часов не
  читает.
- `QuickInput` — frozen dataclass со следующими полями:
  - `kind: TransactionKind` — только `EXPENSE` или `INCOME`;
  - `amount: Decimal` — без округления;
  - `currency_code: str | None`;
  - `comment: str | None`;
  - `category_ref: str | None` — текст после `#` без самого `#`;
  - `account_ref: str | None`;
  - `occurred_on: date | None` — `None`, если `!дата` не указана;
  - `warnings: tuple[QuickInputWarning, ...]`.
- При ошибке поднимается `QuickInputError(code: QuickInputErrorCode)`.
  Коды — `StrEnum`, тексты к ним лежат в `formatters/errors.py`, а не в
  парсере.
- Знак: `+` — доход, `-` или отсутствие знака — расход.
- Сумма:
  - дробный разделитель `.` или `,`;
  - пробелы между разрядами допустимы: первая группа из 1–3 цифр, каждая
    следующая ровно из 3 (`1 200,50`);
  - суффикс `k` или `к` в любом регистре умножает сумму на 1000 (`3k`,
    `1.5к`).
  - Если сумма не разбирается в `Decimal` — ошибка `invalid_amount`.
  - Если сумма не лежит в `(0, 1e12)` — ошибка `amount_out_of_range`.
  - `float` нигде не появляется.
- Валюта — это токен сразу после суммы:
  - ISO-код в любом регистре, если он есть среди доменных констант валют;
  - или символ `₽`, `$`, `€`, стоящий как отдельный токен либо вплотную
    к сумме с любой стороны (`$50`, `50$`).

  Трёхбуквенное слово, которого нет в справочнике, — это обычное слово
  комментария, а не ошибка (раздел 6.6).
- Токены `#…`, `@…` и `!…` извлекаются из остатка строки в любом
  порядке. Остальные слова, соединённые одним пробелом, образуют
  комментарий; если слов не осталось, комментарий `None`.
  - Пустой маркер — `#`, `@` или `!` без текста — ошибка `empty_marker`.
  - Повтор одного маркера — ошибка `duplicate_marker`.
- Дата:
  - `вчера` в любом регистре — `today - 1`;
  - `дд.мм` — год берётся из `today`;
  - `дд.мм.гггг`;
  - несуществующая дата вроде `31.02` или другой формат — ошибка
    `invalid_date`.

  Проверки «не позже завтра» и «не раньше `opened_on`» в парсер не
  входят (раздел 6.6).
- Комментарий длиннее 500 символов обрезается до 500, а в `warnings`
  добавляется `QuickInputWarning.COMMENT_TRUNCATED`.
- Пустая строка или строка без суммы в начале — `invalid_amount`.

**2. `formatters/`** — четыре модуля. Каждый возвращает `str`, aiogram
не импортирует, а пользовательский текст экранирует через `html.escape`.

- `money.py` — `format_money(amount: Decimal, currency_code: str) -> str`:
  - разряды разделяются неразрывным пробелом ` `, дробная часть — через
    запятую;
  - дробная часть показывается с `minor_unit` знаками, если валюта есть в
    справочнике, а иначе с 2 знаками;
  - нулевая дробная часть опускается;
  - округление — `ROUND_HALF_UP`;
  - для `RUB`, `USD`, `EUR` ставится символ после суммы (`1 200,50 ₽`),
    для остальных валют — код;
  - отрицательная сумма начинается с `-`.
- `dates.py`:
  - `format_date(d: date) -> str` в виде `24.09.2026`;
  - `format_period(start: date, end: date) -> str` для полуинтервала
    `[start, end)`:
    - один день — `format_date(start)`;
    - ровно календарный месяц — «сентябрь 2026», название месяца в
      именительном падеже со строчной буквы;
    - иначе `start` — `end - 1 день` через « — ».
- `reports.py`:
  - `render_balances(BalancesDTO) -> str`: строка на каждый счёт и
    итоговая строка;
  - `render_period_summary(PeriodSummaryDTO) -> str`: заголовок с
    периодом, итоги расходов и доходов, разбивка по категориям с
    сортировкой по убыванию суммы; при пустом периоде — отдельная фраза
    вместо нулевых итогов;
  - `render_transaction_card(...) -> str` — текст карточки подтверждения
    из 6.5 на готовых значениях. Параметры: `kind`, `amount`,
    `currency_code`, `account_name`, `category_name: str | None`,
    `occurred_on`, `comment: str | None`, `warnings: Sequence[str]` (уже
    готовые тексты предупреждений);
  - `render_undo(UndoResultDTO) -> str` — подтверждение сторно с суммой и
    датой исходной операции.
- `errors.py`:
  - `error_message(exc: Exception) -> str` — ищет текст по типу
    исключения в словаре с учётом MRO. Для `QuickInputError` текст
    выбирается по коду. Если записи нет, возвращается общий текст «Что-то
    пошло не так, попробуйте ещё раз».
  - В словаре есть записи для всех кодов `QuickInputErrorCode`, а также
    для `CurrencyMismatchError`, `InvariantViolationError`,
    `AlreadyReversedError`, `NotFoundError`, `InvalidCommandError` и
    `DuplicateError`.
  - Формулировки брать из таблицы 6.6, где строка там есть.
  - `warning_message(code: str) -> str` возвращает тексты
    предупреждений: обрезка комментария и округление суммы до
    `minor_unit`. Хендлер подзадачи 14 передаёт сюда свой код
    предупреждения о округлении, поэтому этот код объявить здесь же, как
    `StrEnum` `BotWarning` с кодами `comment_truncated` и `amount_rounded`.
    Значение `QuickInputWarning.COMMENT_TRUNCATED` совпадает с
    `comment_truncated`.

## Границы

- Изменения только в `src/finplan/entrypoints/bot/parsers/` и
  `src/finplan/entrypoints/bot/formatters/`. `git diff --stat` за
  пределы этих двух каталогов не выходит.
- `domain/`, `application/`, `infrastructure/`, `docs/` и `tests/` не
  изменяются. Новые тесты пишет `tester` в подзадаче 15a. Существующие
  тесты, включая `tests/unit/test_layering.py`, остаются зелёными.
- Не импортируются `aiogram`, SQLAlchemy и ничего из `infrastructure`.
  Из `application` разрешены только DTO, `errors.py` и `DuplicateError`.
- Новые зависимости в `pyproject.toml` не добавляются.
- Хендлеры, клавиатуры, роутеры и `bot.py` не создаются: это подзадачи
  12b, 13 и 14.

## Критерий приёмки

- Существуют файлы `parsers/quickinput.py`, `formatters/money.py`,
  `formatters/dates.py`, `formatters/reports.py` и
  `formatters/errors.py` с перечисленными публичными именами.
- `grep -rn "float\|aiogram" src/finplan/entrypoints/bot/parsers src/finplan/entrypoints/bot/formatters`
  ничего не находит.
- Разбор пяти примеров из таблицы 6.5 проверен вызовом
  `uv run python -c ...`, результат приведён в отчёте. Для `-3k такси
  @наличные !вчера`: `amount == Decimal("3000")`,
  `account_ref == "наличные"`, `occurred_on == today - 1`.
- `make test` и `make lint` зелёные.

## Результат исполнителя

- **Сделано.** Написан `parsers/quickinput.py`: функция
  `parse_quick_input(text, *, today)` разбирает строку по грамматике 6.5
  через один якорный regex для блока «знак+валюта-символ+сумма+суффикс
  k/к+валюта-символ», затем токенизирует остаток строки для определения
  валюты-кода/символа отдельным токеном и извлечения маркеров `#`, `@`,
  `!` в любом порядке и порядке следования; всё, что не маркер и не
  валюта, — слова комментария в исходном порядке. `QuickInput` —
  frozen dataclass с указанными в задании полями; `QuickInputError` несёт
  `QuickInputErrorCode` (`invalid_amount`, `amount_out_of_range`,
  `empty_marker`, `duplicate_marker`, `invalid_date`); справочник валют
  парсера — только доменные константы `RUB`, `USD`, `EUR` из
  `domain/common/currency.py` (другого справочника у домена сейчас нет).
  Написаны четыре модуля форматтеров: `money.py` (группировка разрядов
  через НБП, округление `ROUND_HALF_UP` через `MONEY_ROUNDING_CONTEXT` из
  `domain/common/money.py`, символ для RUB/USD/EUR и код для остальных
  валют), `dates.py` (`format_date`, `format_period` с частными случаями
  «один день» и «календарный месяц»), `reports.py` (`render_balances`,
  `render_period_summary` с сортировкой категорий по убыванию и фразой
  для пустого периода, `render_transaction_card`, `render_undo`; весь
  пользовательский текст экранируется `html.escape`) и `errors.py`
  (`error_message` по MRO типа исключения с отдельной веткой для
  `QuickInputError` по коду, `warning_message` и `StrEnum BotWarning` с
  `comment_truncated`/`amount_rounded`).
- **Проверка.** `uv run pytest -q` — `219 passed in 10.33s`. `make lint`
  — все четыре шага (`build-brief.py --check`, `ruff check`, `ruff format
  --check`, `mypy src`) зелёные: `Success: no issues found in 94 source
  files`. `grep -rn "float\|aiogram" src/finplan/entrypoints/bot/parsers
  src/finplan/entrypoints/bot/formatters` — пусто. Пять примеров из
  таблицы 6.5 проверены `uv run python -c ...`:
  - `-1200 кофе` → `EXPENSE, amount=Decimal('1200'), comment='кофе'`
  - `1200 кофе` → то же, `EXPENSE` без знака
  - `+85000 зарплата` → `INCOME, amount=Decimal('85000'), comment='зарплата'`
  - `-3k такси @наличные !вчера` → `EXPENSE, amount=Decimal('3000'),
    account_ref='наличные', occurred_on=date(2026, 9, 23)` (при
    `today=date(2026, 9, 24)`), что совпадает с требованием критерия
  - `-50 usd отель #travel` → `EXPENSE, amount=Decimal('50'),
    currency_code='USD', category_ref='travel', comment='отель'`
- **Решения и отложенное.** Формулировки ошибок и предупреждений, для
  которых в таблице 6.6 нет дословной строки (`empty_marker`,
  `duplicate_marker`, `invalid_date`, а также тексты для
  `CurrencyMismatchError`, `InvariantViolationError`,
  `AlreadyReversedError`, `NotFoundError`, `InvalidCommandError`),
  написаны по смыслу соответствующего исключения/кода — таблица даёт
  дословный текст только для `invalid_amount` и `amount_out_of_range`,
  текст для `DuplicateError` («Уже сохранено») взят дословно из раздела
  2.2. `render_transaction_card` и `render_period_summary` не следуют
  конкретному текстовому шаблону — в разделах 6.5/6.6 нет утверждённого
  дословного текста карточки/отчёта, только перечень обязательных
  элементов, которые в отчёт включены. Проверки «не позже завтра», «не
  раньше `opened_on`», «сумма ≤ minor_unit» и валидность
  счёта/категории — сознательно не в парсере, это граница 6.6, их место
  в хендлере подзадачи 14. Тесты на парсер и форматтеры не написаны —
  это отдельная подзадача 15a у `tester`, по границам задания.
- **Вопросы диспетчеру.** Нет.

## Приёмка диспетчером

Принято с двумя правками диспетчера. Первая: регулярное выражение суммы
не требовало границы после числа, поэтому «1 2000» разбиралось как 1200
с комментарием «0», а «3kg» — как 3000 с комментарием «g». Добавлен
lookahead `(?=\s|$)`: теперь «1 2000» — это 1 с комментарием «2000», а
«3kg» — ошибка `invalid_amount`. Вторая: текст `amount_out_of_range`
«Сумма должна быть больше нуля» вводил в заблуждение при сумме от 1e12;
текст и строка таблицы 6.6 заменены на «Сумма должна быть больше нуля и
меньше триллиона». Тесты на оба случая входят в подзадачу 15a.
