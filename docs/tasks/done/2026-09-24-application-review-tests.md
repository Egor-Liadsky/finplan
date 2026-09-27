# Недостающие тесты use case этапа 1 по итогам ревью

- **Исполнитель:** tester
- **Слой:** application
- **Раздел архитектуры:** docs/architecture.md, разделы 2.2, 3.1, 11.1, 11.2
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 7d плана `docs/tasks/2026-09-23-stage1-plan.md`. Ревью слоя
application нашло пропуски в тестах
(`docs/tasks/2026-09-24-application-tests-review.md`), а подзадача 7c
исправила код (`docs/tasks/2026-09-24-application-review-fixes.md`, раздел
«Результат исполнителя» — прочитать его первым, чтобы знать точные тексты
и места исправлений). Эта подзадача покрывает тестами и старые пропуски, и
новое поведение из 7c.

`make test` и `make lint` зелёные после 7c.

До первой правки прочитать:

- `docs/architecture-brief.md` — правила денег и тестов;
- `docs/architecture.md` через `Read` с `offset` и `limit`: 2.2 — строки
  379–433; 3.1 — 436–484 (таблица округления); 11.1 — 2782–2798; 11.2 —
  2799–2825. Если номера строк разошлись с картой в выжимке, верна карта в
  выжимке;
- `tests/unit/application/conftest.py` и `tests/unit/application/fakes.py`
  — кусками, только фикстуры и методы, нужные для новых тестов; заглушки
  уже умеют запоминать, с каким `user_id` открывалась каждая транзакция и
  закоммичена ли она;
- по одному существующему тесту в каждом файле, куда добавляются новые, —
  чтобы писать в том же стиле.

## Задание

Дописать тесты в существующие файлы `tests/unit/application/`. Суммы —
строками через `Decimal("...")`, никогда `float`.

**Пропуски, найденные ревью:**

1. `test_record_transaction.py` — категория другого вида: расход с
   категорией вида `income` и доход с категорией вида `expense` дают
   `InvalidCommandError`, и ничего не закоммичено.
2. `test_get_balances.py` — несуществующий пользователь даёт
   `NotFoundError`.
3. `test_period_summary.py` — несуществующий пользователь даёт
   `NotFoundError`.
4. `test_period_summary.py` — граница полуинтервала `[from, to)` для
   `scope="month"` в таймзоне пользователя, отличной от UTC: операция ровно
   в первый момент месяца по местному времени попадает в сводку, операция
   ровно в первый момент следующего месяца — нет. Сейчас так проверен
   только `scope="day"`.

**Новое поведение из 7c:**

5. `test_record_transaction.py` — округление по разделу 3.1:
   `Decimal("10.005")` в RUB сохраняется как `Decimal("10.01")`, а
   `Decimal("10.004")` — как `Decimal("10.00")`; `amount` и `base_amount`
   сохранённой операции равны. Если в заглушках доступна валюта с
   `minor_unit = 0`, проверить и её; если нет — не добавлять её ради теста и
   написать об этом в результате.
6. `test_record_transaction.py` — сумма, обнуляющаяся при округлении
   (`Decimal("0.004")` в RUB), даёт `InvalidCommandError`, и ничего не
   закоммичено.
7. `test_register_user.py` — начальный остаток счёта округляется тем же
   правилом.
8. `test_register_user.py` — синтаксически неверная таймзона (ключ с `..`)
   даёт `InvalidCommandError`, как и неизвестная.
9. `test_register_user.py` — повторный `/start` уже зарегистрированного
   пользователя: первая транзакция открыта с `user_id = None`, транзакций от
   имени нового случайного `id` не открывается, ничего не закоммичено,
   `created` равен `False`.

Тесты проверяют правило, а не реализацию: утверждения — о сохранённых
данных, результате и брошенной ошибке, а не о вызовах методов.

## Границы

- изменяются только файлы `tests/unit/application/test_*.py`; `fakes.py` и
  `conftest.py` правятся только если без этого тест не написать, и тогда
  правка описывается в результате с причиной;
- `src/` и `docs/` не изменяются, кроме раздела `## Результат исполнителя`
  в этом файле — проверяется `git diff --stat`;
- если тест выявляет дефект в `src/`, не чинить: пометить тест
  `xfail(strict=True)` с причиной и вынести в «Вопросы диспетчеру».

## Критерий приёмки

- `make test` зелёный, число тестов выросло не меньше чем на 10;
- `make lint` зелёный;
- `uv run mypy --strict tests/unit/application` без ошибок;
- `grep -rn "float" tests/unit/application` пуст;
- каждый из девяти пунктов задания назван в результате с именем теста.

## Результат исполнителя

**Сделано.**

Дописаны тесты только в `tests/unit/application/test_*.py`; `fakes.py` и
`conftest.py` не менялись — под все девять пунктов существующих фикстур
хватило.

1. `test_record_transaction.py::test_category_of_wrong_kind_raises_invalid_command`
   — параметризован обеими комбинациями (`EXPENSE`/`income`-категория и
   `INCOME`/`expense`-категория); проверяет `InvalidCommandError`, пустой
   `store.transactions` и `committed is False` у последней открытой
   транзакции.
2. `test_get_balances.py::test_missing_user_raises_not_found` —
   несуществующий `user_id` даёт `NotFoundError`.
3. `test_period_summary.py::test_missing_user_raises_not_found` — то же для
   `GetPeriodSummary`.
4. `test_period_summary.py::test_month_boundary_from_is_included_and_to_is_excluded`
   — по образцу уже существующего `test_day_boundary_...`, но для
   `scope="month"`: операция ровно в 00:00 по Москве 1 марта попадает в
   свод, операция ровно в 00:00 по Москве 1 апреля — нет.
5. `test_record_transaction.py::test_amount_is_rounded_half_up_to_minor_unit_and_matches_base_amount`
   (параметризован `Decimal("10.005") → Decimal("10.01")` и
   `Decimal("10.004") → Decimal("10.00")` в RUB) — сверяет и `result.amount`,
   и сохранённые `stored.amount.amount`/`stored.base_amount`. Валюты с
   `minor_unit = 0` (например, JPY) в наборе, который знают `fakes.py` и
   `conftest.py` (`RUB`, `USD`, `EUR` — у всех `minor_unit = 2`), нет;
   по границам задания она туда не добавлялась, тест это утверждение
   проверяет только на RUB — отмечено докстрингом в файле теста.
6. `test_record_transaction.py::test_amount_rounding_to_zero_raises_invalid_command`
   — `Decimal("0.004")` RUB (проходит `Field(gt=0)` DTO, но округляется до
   нуля) даёт `InvalidCommandError`, `store.transactions` пуст, последняя
   транзакция не закоммичена.
7. `test_register_user.py::test_opening_balance_is_rounded_half_up_to_minor_unit`
   (параметризован теми же двумя значениями, что пункт 5) — сверяет
   `opening_balance.amount` сохранённого счёта. По той же причине, что в
   пункте 5, проверено только на RUB.
8. `test_register_user.py::test_malformed_timezone_key_raises_invalid_command_error`
   — `timezone="Europe/.."` (`ZoneInfo` бросает `ValueError`, а не
   `ZoneInfoNotFoundError`, как для просто неизвестного ключа) даёт
   `InvalidCommandError`; отдельно проверено, что ничего не создано и не
   открыто ни одной транзакции.
9. `test_register_user.py::test_repeat_registration_looks_up_existing_user_without_new_id_transaction`
   — после первой регистрации счётчик открытых транзакций фабрики
   очищается, затем при повторном `/start` проверяется: первая открытая
   транзакция — с `user_id=None` (поиск по `telegram_id`); ни одна из
   транзакций повторной регистрации не открыта с `user_id`, отличным от
   `None` или уже существующего `first.user.id` (то есть ни с одним новым
   случайным id); ни одна не закоммичена; `created is False`.

Все новые утверждения — про сохранённые данные, результат и брошенную
ошибку, а не про вызовы методов заглушек.

**Проверка.**

- `make test` (`uv run pytest`) — `149 passed in 7.38s` (было 137 до этой
  задачи, прирост 12 тестов, критерий «не меньше 10» выполнен).
- `make lint` (`build-brief.py --check`, `ruff check`, `ruff format --check`,
  `mypy src`) — все шаги зелёные, включая сверку `architecture-brief.md` с
  документом.
- `uv run mypy --strict tests/unit/application` — `Success: no issues found
  in 10 source files`.
- `grep -rn "float" tests/unit/application` — пусто (код возврата 1, совпадений
  нет).
- `git diff --stat` — изменены только `test_get_balances.py`,
  `test_period_summary.py`, `test_record_transaction.py`,
  `test_register_user.py` (плюс этот файл задачи); `fakes.py`, `conftest.py`,
  `src/`, остальной `docs/` не тронуты.

**Решения и отложенное.**

- Валюта с `minor_unit = 0` не добавлена ни в `fakes.py`, ни в
  `conftest.py`, ни локально в тестовом файле — граница задания разрешает
  не добавлять её ради теста, если её нет в заглушках; вместо этого в
  докстрингах тестов пунктов 5 и 7 явно написано, что проверка ограничена
  RUB. Это единственное отклонение от буквы пунктов 5 и 7 — по существу
  правила округления оно всё равно покрыто двумя контрольными значениями
  из раздела 3.1 (`.005` вверх, `.004` вниз) на границе минорной единицы.
- Дефектов в `src/`, которые новые тесты обнаружили бы, нет — весь новый
  код 7c (округление, разбор таймзоны, порядок поиска пользователя) прошёл
  без `xfail`.
- Формулы раздела 11.2 (контрольные примеры / сверка с эталоном /
  hypothesis-свойства) к этой подзадаче впрямую не применялись: все девять
  пунктов — про округление одной суммы по фиксированному правилу и про
  границы UoW/времени в use case, а не про расчётный слой `domain/finance`
  из раздела 5, где эти три приёма нужны в полном составе.

**Вопросы диспетчеру.**

Нет.
