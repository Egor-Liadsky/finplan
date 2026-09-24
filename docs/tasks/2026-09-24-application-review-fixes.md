# Исправление находок ревью слоя application: округление, таймзона, поиск при регистрации

- **Исполнитель:** developer
- **Слой:** application
- **Раздел архитектуры:** docs/architecture.md, разделы 2.2, 3.1, 3.3
- **Заведена:** 2026-09-24

## Входные условия

Это подзадача 7c плана `docs/tasks/2026-09-23-stage1-plan.md`. Ревью слоя
application закрыто двумя файлами задач:
`docs/tasks/2026-09-24-application-code-review.md` (код) и
`docs/tasks/2026-09-24-application-tests-review.md` (тесты). Диспетчер
сверил находки с кодом и документом; здесь — те, что исправляются в `src/`.
Недостающие тесты пишет `tester` следующей подзадачей 7d после этой.

`make test` (136 passed, 1 xfailed) и `make lint` зелёные на `d46e98f`.

До первой правки прочитать:

- `docs/architecture-brief.md` — правила слоёв и денег;
- `docs/architecture.md` через `Read` с `offset` и `limit`: 2.2 — строки
  379–433; 3.1 — 436–484 (таблица округления). Если номера строк
  разошлись с картой в выжимке, верна карта в выжимке;
- `src/finplan/application/use_cases/transactions/record_transaction.py`;
- `src/finplan/application/use_cases/auth/register_user.py`;
- `src/finplan/domain/common/money.py`, строки 85–89
  (`Money.round_to_minor_unit`);
- `tests/unit/application/test_register_user.py`, строки 140–170.

## Задание

Три правки в двух use case.

**1. Округление суммы, введённой пользователем.** Раздел 3.1, таблица
округления: хранение операции, введённой пользователем, — `ROUND_HALF_UP`
до `minor_unit` валюты. Сейчас `RecordTransaction` кладёт
`command.amount` в `Money` и в `base_amount` как есть
(`record_transaction.py:78` и `:83`), поэтому, например, `10.005` RUB или
`100.5` JPY попадают в журнал с лишней точностью. Требуется:

- в `RecordTransaction` сумму операции округлять
  `Money(command.amount, account.currency).round_to_minor_unit()` и её же
  значение класть в `base_amount` — на этапе 1 курс равен 1, и две суммы
  обязаны совпадать до знака;
- если после округления сумма равна нулю (например, `0.004` RUB), бросать
  `InvalidCommandError` до создания `Transaction`, а не отдавать это
  доменному инварианту;
- в `RegisterUser` тем же способом округлять начальный остаток счёта
  (`register_user.py:64`): это тоже сумма, введённая пользователем. Ноль
  после округления здесь допустим — нулевой начальный остаток разрешён.

**2. Неизвестная таймзона.** Раздел 2.2: команда, противоречащая данным, —
`InvalidCommandError` сценария. Сейчас `ZoneInfo(command.timezone)` внутри
`RegisterUser` (`register_user.py:48`) бросает `ZoneInfoNotFoundError`.
Исправление ложится в use case, а не в DTO: рядом уже стоит такая же
проверка кода валюты. Требуется:

- разбирать таймзону в начале `__call__`, до открытия Unit of Work, рядом с
  проверкой валюты; `ZoneInfoNotFoundError` и `ValueError` (его `ZoneInfo`
  бросает на синтаксически неверный ключ, например с `..`) превращать в
  `InvalidCommandError` с понятным текстом;
- снять `@pytest.mark.xfail(...)` с
  `test_unknown_timezone_raises_invalid_command_error` в
  `tests/unit/application/test_register_user.py`: с `strict=True` тест иначе
  упадёт как `XPASS`. Тело теста не менять. Это единственная правка в
  `tests/`.

**3. Поиск существующего пользователя с `user_id = None`.** Раздел 2.2:
фабрика Unit of Work принимает `None` только для поиска пользователя по
`telegram_id`, пока его `id` неизвестен. Сейчас `RegisterUser` ищет
существующего пользователя в транзакции, открытой от имени только что
сгенерированного `new_id` (`register_user.py:44–45`). Под RLS из раздела 4.5
такой поиск будет промахиваться, и каждый повторный `/start` пойдёт через
неудачную вставку. Требуется:

- сначала искать по `telegram_id` в отдельной транзакции
  `self._uow_factory(None)`; если пользователь найден — сразу переходить к
  ветке «уже зарегистрирован», ничего не создавая;
- только если не найден — открывать транзакцию от имени `new_id` и
  создавать пользователя, счёт и дерево категорий, как сейчас;
- ветку `except DuplicateError` для гонки двух `/start` сохранить: после неё
  повторный поиск с `None` и ветка «уже зарегистрирован», как сейчас.

Поведение, наблюдаемое вызывающей стороной, кроме пунктов 1 и 2, не
меняется: тот же `RegisterUserResult`, тот же флаг `created`.

## Границы

- изменяются только `record_transaction.py`, `register_user.py` и
  маркер `xfail` в `test_register_user.py`; остальные файлы `src/`, `tests/`
  и `docs/` не изменяются — проверяется `git diff --stat`;
- сигнатуры портов, DTO и `application/errors.py` не меняются;
- `src/finplan/domain/` не изменяется;
- новые тесты не пишутся — это подзадача 7d; если существующий тест падает
  из-за правки, не чинить его, а описать в результате, какой и почему;
- `docs/dev-log.md` не правится.

## Критерий приёмки

- `make test` зелёный, `xfailed` в итоговой строке нет;
- `make lint` зелёный;
- `grep -n "round_to_minor_unit" src/finplan/application/use_cases/transactions/record_transaction.py src/finplan/application/use_cases/auth/register_user.py`
  находит оба файла;
- `grep -n "ZoneInfoNotFoundError" src/finplan/application/use_cases/auth/register_user.py`
  находит перехват;
- в `register_user.py` первый вызов `self._uow_factory` принимает `None`;
- `git diff --stat` показывает только три названных файла, не считая этот
  файл задачи.

## Результат исполнителя

_Заполняет исполнитель. Выше этой строки ничего не меняется._
