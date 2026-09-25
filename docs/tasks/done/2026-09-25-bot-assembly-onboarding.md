# Сборка бота: container, middleware, онбординг, common и fallback

- **Исполнитель:** developer
- **Слой:** entrypoints и корень композиции `src/finplan/container.py`
- **Раздел архитектуры:** docs/architecture.md, разделы 2.1, 2.2, 6.1,
  6.2, 6.3, 6.4, 6.6, 6.7, 12.1, 12.2
- **Этап:** 1, подзадача 12b из `docs/tasks/2026-09-23-stage1-plan.md`
- **Заведена:** 2026-09-25

## Входные условия

Домен, `application` и `infrastructure` этапа 1 готовы и покрыты
тестами. Парсер быстрого ввода и форматтеры лежат в
`entrypoints/bot/parsers/` и `entrypoints/bot/formatters/` (подзадача
12a). Диспетчер уже добавил два файла инфраструктуры, которые здесь
нужно использовать, а не переписывать:
`src/finplan/infrastructure/clock.py` (`SystemClock`) и
`src/finplan/infrastructure/telegram/bot.py` (`create_bot` с
`parse_mode=HTML`).

Непосредственно перед этой задачей в `docs/architecture.md` дописаны
решения, по которым она выполняется. В 6.2 — строки таблицы роутеров,
абзацы «Регистрация», «Команды посреди диалога», порядок middleware и
`Container` в `workflow_data`. В 6.3 — `Onboarding` и абзац
«Онбординг». В 6.7 — абзац «Меню по этапам».

До первой правки прочитать:

- `docs/architecture-brief.md`, затем разделы 6.2, 6.3 и 6.7 целиком,
  6.1, 6.6, 12.1 и 12.2 — по номерам строк из карты;
- `src/finplan/entrypoints/bot/main.py` и `routers/start.py` — заглушки
  этапа 0, их предстоит заменить;
- конструкторы use case в `src/finplan/application/use_cases/*/*.py`
  (строка `def __init__` у каждого) и DTO в
  `src/finplan/application/dto/auth.py`;
- `bind_context` и `clear_context` в `src/finplan/logging.py`;
- `src/finplan/entrypoints/bot/formatters/errors.py` целиком и
  `parse_quick_input` с `_parse_amount` в `parsers/quickinput.py`;
- сборку `SqlAlchemyUnitOfWorkFactory` в
  `tests/integration/repositories/conftest.py`, строка около 120;
- комментарий о переменных окружения при импорте `bot/main.py` в
  `tests/conftest.py`, строки 48–75.

Файлы читать нужными кусками, а не целиком.

## Задание

1. **`src/finplan/container.py`.** Frozen dataclass `Container` с полями
   `clock`, `uow_factory` и по одному полю на каждый существующий use
   case: `register_user`, `find_user`, `list_accounts`, `get_balances`,
   `list_categories`, `record_transaction`, `undo_last`,
   `period_summary`. Функция `build_container(settings: Settings)`
   создаёт engine и sessionmaker через `infrastructure/db/engine.py`,
   фабрику `SqlAlchemyUnitOfWorkFactory` с `SqlAlchemyLedgerQueries`,
   `SystemClock` и use case. Освобождение ресурсов — `async def
   aclose()` у контейнера, которая вызывает `engine.dispose()`. Engine
   поэтому хранится в контейнере, а не только в замыкании. К базе
   `build_container` не подключается.

2. **`parse_amount` в `parsers/quickinput.py`.** Публичная функция
   `parse_amount(text: str) -> Decimal`. Вся строка — одна сумма в
   синтаксисе быстрого ввода без знака, без валюты и без комментария.
   Те же проверки диапазона и те же коды `QuickInputError`, что у
   `parse_quick_input`. Существующее регулярное выражение и
   `_parse_amount` переиспользовать, а не дублировать. Функцию берут
   шаг `opening_balance` онбординга и шаг суммы диалогов подзадачи 13.

3. **Код ошибки неизвестной таймзоны.** В `formatters/errors.py`
   добавить enum `BotInputError(StrEnum)` с кодом
   `UNKNOWN_TIMEZONE = "unknown_timezone"`, функцию
   `input_error_message(code)` и текст «Не знаю такую таймзону. Пример:
   Europe/Moscow». Тексты по-прежнему только в этом модуле.

4. **`bot/states.py`.** `StatesGroup` этапа 1 в точности по коду
   раздела 6.3: `AddExpense`, `AddIncome`, `QuickConfirm`, `Onboarding`.
   Группы других этапов (`AddTransfer`, `AddValuation`, `AddGoal`,
   `AddDeposit`) не добавлять.

5. **Middleware в `bot/middlewares/`.** По файлу на middleware:
   `logging.py`, `errors.py`, `user.py`. Поведение, место подключения
   и порядок — раздел 6.2, абзац «Middleware». Дополнительно:
   - `LoggingMiddleware` не пишет в лог текст сообщения (раздел 12.1);
   - `ErrorMiddleware` распознаёт известные ошибки: `QuickInputError`,
     `DomainError`, `ApplicationError`, `DuplicateError`. Их текст берётся
     через `error_message`, трейс не логируется. На сообщение отвечает
     `message.answer`, на нажатие кнопки — `callback.answer` плюс
     `message.answer` в чат кнопки. Если отправить ответ не удалось,
     это логируется, а исключение наружу не выпускается;
   - `UserMiddleware` зовёт `container.find_user`, в репозиторий не
     ходит.

6. **Клавиатуры в `bot/keyboards/`.** `onboarding.py` — кнопки трёх
   первых шагов онбординга и кнопка «Начать с нуля». `menu.py` — главное
   меню этапа 1 и подменю «Добавить», «Счета», «Отчёты» по абзацу «Меню
   по этапам» раздела 6.7, а также reply-клавиатура из двух кнопок.
   `callback_data` — через фабрики `CallbackData` aiogram, префиксы —
   из 6.7. Длина каждого значения укладывается в 64 байта.

7. **Роутеры в `bot/routers/`.**
   - `start.py` — `/start` и `/help` и все шаги `Onboarding` по абзацу
     «Онбординг» раздела 6.3. В конце вызывается `container.register_user`
     с `RegisterUserCommand`, а данные Telegram берутся из
     `message.from_user`. Текст `/help` перечисляет команды этапа 1 и
     синтаксис быстрого ввода с тремя примерами из таблицы 6.5.
   - `common.py` — `/cancel` (очистить состояние и ответить, было ли что
     отменять), `/menu`, `nav:*` и две кнопки reply-клавиатуры. Главное
     меню перерисовывается через `edit_message_text` на нажатие кнопки и
     отправляется новым сообщением на команду или текст.
   - `fallback.py` — по строке таблицы 6.2.
   - `undo.py`, `expense.py`, `income.py`, `accounts.py`, `reports.py`,
     `quick.py` — только `router = Router(name=...)` без хендлеров и
     docstring, где сказано, какая подзадача плана их наполнит (13
     или 14).

   Хендлеры шагов онбординга не принимают текст, начинающийся с `/`
   (абзац «Команды посреди диалога» раздела 6.2). Пользовательский
   текст, попадающий в ответ, экранируется через `html.escape`.

8. **`bot/main.py`.** Функция `create_dispatcher(container: Container,
   storage: BaseStorage) -> Dispatcher` подключает middleware и роутеры в
   порядке раздела 6.2: `start.router` — напрямую, остальные — внутри
   `registered`. Контейнер кладётся в `workflow_data` под ключом
   `container`. `main()` строит контейнер, бот через `create_bot`,
   хранилище по-прежнему выбирается по `REDIS_URL` и регистрирует команды
   этапа 1 через `set_my_commands`: `start`, `help`, `menu`, `expense`,
   `income`, `balance`, `today`, `month`, `undo`, `cancel`, с описаниями
   из таблицы 6.1. В `finally` закрываются сессия бота и контейнер.
   Модульные `bot` и `dp` убрать, если на них больше ничего не
   ссылается: `create_dispatcher` нужен интеграционным тестам
   подзадачи 15b, а объекты уровня модуля им мешают. Если убрать их
   нельзя, объяснить в результате почему.

## Границы

- Изменяются только `src/finplan/container.py` и файлы в
  `src/finplan/entrypoints/bot/`. `domain`, `application`,
  `infrastructure`, `docs/` и `tests/` не трогать. Исключение:
  комментарий в `tests/conftest.py` про `bot = Bot(...)` можно
  исправить, если объект уровня модуля убран.
- Бизнес-логики в хендлерах нет: разбор входа, вызов use case,
  форматирование ответа (раздел 2.2). Проверка таймзоны по
  `available_timezones()` — разбор входа, она допустима.
- `ThrottlingMiddleware` и `RedisStorage`-специфичную настройку не
  писать: Redis появляется на этапе 2.
- Новых зависимостей в `pyproject.toml` нет.
- Тесты не писать: это подзадачи 15a и 15b. Существующие тесты должны
  остаться зелёными, включая `tests/unit/test_layering.py`.
- Если раздел 6.2, 6.3 или 6.7 не отвечает на вопрос или противоречит
  себе, записать вопрос в результат и остановиться, а не решать самому.

## Критерий приёмки

- `make lint` и `make test` зелёные.
- `uv run python -c "from finplan.container import build_container; from
  finplan.config import get_settings; from
  finplan.entrypoints.bot.main import create_dispatcher; from
  aiogram.fsm.storage.memory import MemoryStorage;
  create_dispatcher(build_container(get_settings()), MemoryStorage())"`
  завершается без ошибок при переменных окружения из `.env.example`.
- `git diff --stat` показывает изменения только в путях из раздела
  «Границы».
- В результате перечислены: порядок подключения роутеров, как на деле
  подключён `UserMiddleware` (событие и уровень) и все тексты,
  придуманные исполнителем, а не взятые из документа.

## Результат исполнителя

**Сделано.**

Собран корень композиции `src/finplan/container.py`: frozen dataclass
`Container` с `clock`, `uow_factory`, полями на восемь use case этапа 1 и
`engine`; `build_container(settings)` строит `AsyncEngine` и
`async_sessionmaker` через `infrastructure/db/engine.py`,
`SqlAlchemyUnitOfWorkFactory` с `SqlAlchemyLedgerQueries`, `SystemClock` и
use case — без единого обращения к сети. `Container.aclose()` вызывает
`engine.dispose()`.

`parsers/quickinput.py` получил публичную `parse_amount(text) -> Decimal`:
переиспользует `_AMOUNT_RE`/`_parse_amount`, требует, чтобы вся строка (без
знака, без валюты, без хвостового текста) была одной суммой, и поднимает те
же `QuickInputError` с теми же кодами, что `parse_quick_input`.

`formatters/errors.py` получил `BotInputError(StrEnum)` с
`UNKNOWN_TIMEZONE` и `input_error_message(code)` — единственная точка,
где лежит текст «Не знаю такую таймзону. Пример: Europe/Moscow».

`bot/states.py` — `AddExpense`, `AddIncome`, `QuickConfirm`, `Onboarding`
дословно по разделу 6.3; группы остальных этапов не заведены.

Три middleware в `bot/middlewares/`:

- `LoggingMiddleware` (`dp.update.outer_middleware`, первым в цепочке) —
  привязывает `service=bot`, `request_id=update_id`, `user_id=telegram_id`
  через `bind_context`/`clear_context`, логирует только `update_type`, без
  текста сообщения.
- `ErrorMiddleware` (`dp.update.outer_middleware`, вторым) — ловит
  `QuickInputError | DomainError | ApplicationError | DuplicateError` и
  берёт текст через `error_message`; на прочие исключения пишет трейс и
  отвечает «Не удалось сохранить. Попробуйте ещё раз. Код: `<update_id>`».
  Отвечает `message.answer` на сообщение, `callback.answer()` +
  `callback.message.answer(text)` на кнопку; отправка ответа обёрнута
  отдельным `try` — сбой логируется, наружу не выходит.
- `UserMiddleware` — вызывает `container.find_user`, в репозиторий не
  ходит; при отсутствии пользователя отвечает «Нажмите /start» и не
  пропускает апдейт дальше, иначе кладёт `UserDTO` в `data["user"]`.

**Как на деле подключён `UserMiddleware` (событие и уровень).** Не как
единый `dp.update.outer_middleware`, а как **outer middleware двух
конкретных наблюдателей** родительского роутера `registered`:
`registered.message.outer_middleware(UserMiddleware())` и
`registered.callback_query.outer_middleware(UserMiddleware())` — раздел
6.2 требует его именно «для сообщений и нажатий кнопок», а не для любого
апдейта. Он читает `Container` из `data["container"]` (workflow data), а
не из конструктора: конструктор `UserMiddleware()` без аргументов, поэтому
регистрация в `create_dispatcher` не требует протаскивать контейнер вручную
в каждый middleware.

Клавиатуры: `keyboards/onboarding.py` — четыре фабрики
(`base_currency_keyboard`, `timezone_keyboard`, `account_type_keyboard`,
`opening_balance_keyboard`) через `CallbackData`-класс
`OnboardingCallback(prefix="onb")` с полями `step`/`value`; публичный
`ACCOUNT_TYPE_LABELS` — подпись кнопки становится именем счёта (раздел 6.3,
последний абзац шага `account_type`). `keyboards/menu.py` —
`main_menu_keyboard`, `add_menu_keyboard`, `accounts_menu_keyboard`,
`reports_menu_keyboard`, `reply_keyboard`, плюс `CallbackData`-классы
`NavCallback(prefix="nav")`, `ExpenseCallback(prefix="exp")`,
`IncomeCallback(prefix="inc")`, `AccountsCallback(prefix="acc")`,
`ReportsCallback(prefix="rep")` — четыре последних временно определены
здесь же, рядом с клавиатурой, потому что роутеры, которым они
семантически принадлежат, пока пустые заглушки (см. ниже, «Решения»).
Самое длинное значение `callback_data` — 31 байт, лимит 64 байта не задет.

Роутеры: `start.py` — `/start` (регистрация нового пользователя через
онбординг либо приветствие уже зарегистрированного с показом главного
меню), `/help` (список команд этапа 1 и три примера быстрого ввода из
таблицы 6.5 дословно), все шаги `Onboarding` (валюта и тип счёта —
кнопками, таймзона — кнопкой или текстом с проверкой по
`available_timezones()`, остаток — кнопкой «Начать с нуля» или текстом
через новую `parse_amount`); в конце — вызов `container.register_user` с
данными из `message.from_user`/`callback.from_user`. `common.py` —
`/cancel` (очищает состояние, отвечает по-разному, было ли что отменять),
`/menu`, `nav:*` (правит то же сообщение через `edit_text`), обе кнопки
reply-клавиатуры (отвечают новым сообщением). `fallback.py` — сообщение
получает подсказку, кнопка без обработчика — `callback.answer("Кнопка
устарела")`. `undo.py`, `expense.py`, `income.py`, `accounts.py`,
`reports.py`, `quick.py` — пустой `Router` с docstring, называющим
подзадачу (13 или 14), которая его наполнит; `transfer.py`, `goals.py`,
`deposits.py`, `recurring.py`, `settings.py` не заведены — раздел 6.2
описывает их, но раздел 6.7 «Меню по этапам» явно перечисляет для этапа 1
только «Добавить» (расход/доход), «Счета» (остатки), «Отчёты»
(сегодня/месяц), а задание в пункте 7 называет ровно шесть заглушек и не
называет эти пять — прочитано как «эти роутеры появятся вместе со своими
этапами», а не как пропуск.

`bot/main.py` — `create_dispatcher(container, storage) -> Dispatcher`:
кладёт `container` в `workflow_data` через `Dispatcher(storage=storage,
container=container)`, вешает `LoggingMiddleware`/`ErrorMiddleware` на
`dp.update.outer_middleware` в этом порядке, подключает `start.router`
напрямую, остальные — внутрь `registered` (см. «Порядок роутеров» ниже).
`main()` строит `Container` через `build_container`, `Bot` через
`create_bot`, хранилище — `RedisStorage`/`MemoryStorage` по `REDIS_URL`,
регистрирует `set_my_commands` с десятью командами этапа 1 и описаниями из
таблицы 6.1 (дословно, где были готовые формулировки), в `finally`
закрывает `bot.session` и вызывает `await container.aclose()`.
Модульные `bot`/`dp` убраны: `create_dispatcher` — чистая фабрика без
побочных эффектов, интеграционные тесты подзадачи 15b строят диспетчер сами
через неё.

**Порядок подключения роутеров** (`create_dispatcher`): `start.router` —
напрямую к `dp`; внутри `registered` (за `UserMiddleware`) — `common`,
`undo`, `expense`, `income`, `accounts`, `reports`, `quick`, `fallback` — в
этом порядке, как в таблице 6.2 с пропуском роутеров, которых на этапе 1
ещё нет (`transfer`, `goals`, `deposits`, `recurring`, `settings`).

Исправлен один комментарий в `tests/conftest.py` (разрешено границами
задачи): убрано упоминание модульного `bot = Bot(...)` в
`entrypoints/bot/main.py`, которого больше нет — `TELEGRAM_BOT_TOKEN`
объяснён через `create_bot()` и интеграционные тесты подзадачи 15b.

**Тексты, придуманные исполнителем** (документ их не задаёт дословно):

- подписи одиннадцати кнопок таймзоны — «Калининград (UTC+2)» … «Камчатка
  (UTC+12)» (`keyboards/onboarding.py`);
- заголовки экранов меню — «Главное меню», «Добавить», «Счета», «Отчёты» —
  и кнопка «‹ Назад» в подменю (`keyboards/menu.py`, `routers/common.py`);
  подписи «Расход», «Доход», «Остатки по счетам», «Сегодня», «Этот месяц»
  взяты из подписей узлов диаграммы раздела 6.7 дословно;
- `/cancel`: «Диалог отменён» и «Отменять нечего»;
- `fallback.py`: «Не понял. Наберите /help — там команды и синтаксис
  быстрого ввода.» (документ даёт только смысл «не понял, /help», не
  готовую фразу); «Кнопка устарела» — из документа дословно;
- приглашения на каждом шаге онбординга (`_ONBOARDING_INTRO_TEXT`,
  `_TIMEZONE_PROMPT_TEXT`, `_ACCOUNT_TYPE_PROMPT_TEXT`,
  `_OPENING_BALANCE_PROMPT_TEXT`), приветствие уже зарегистрированного
  (`_WELCOME_BACK_TEXT`) и текст завершения онбординга;
- текст `/help`: структура и формулировки вокруг команд — исполнителя;
  сами описания команд — из таблицы 6.1, примеры быстрого ввода — из
  таблицы 6.5, оба дословно.

**Проверка.**

- `make lint` — зелёный (`build-brief.py --check`, `ruff check`, `ruff
  format --check`, `mypy src`).
- `make test` (`uv run pytest`) — 218 passed, 1 failed:
  `tests/integration/bot/test_start.py::test_start_command_sends_non_empty_reply`
  падает с `TypeError: handle_start() missing 1 required positional
  argument: 'container'`. Тест — артефакт этапа 0 (его же docstring:
  «раздел 13 «Этап 0»»), строит `Dispatcher(storage=MemoryStorage())` без
  `container` в `workflow_data` и напрямую дёргает старый безпараметрный
  `handle_start`. Задание прямо требовало заменить `routers/start.py`
  («заглушки этапа 0, их предстоит заменить») сигнатурой с `state` и
  `container` — новая сигнатура несовместима со старым тестом по
  конструкции, а границы задачи запрещают трогать `tests/` за пределами
  одного разрешённого комментария. Считаю правкой не для этой задачи, см.
  вопрос диспетчеру ниже.
- Критерий приёмки: команда `uv run python -c "from finplan.container
  import build_container; ..."` из задания выполнена дословно, завершилась
  без ошибок (использует переменные окружения, которые `Settings` берёт
  через `pydantic-settings` — в этом окружении есть локальный `.env`,
  которого нет в git).
- `git diff --stat` + `git status --porcelain`: изменены только
  `src/finplan/container.py` (новый), `src/finplan/entrypoints/bot/**`
  (новые и изменённые файлы) и один комментарий в `tests/conftest.py`
  — всё внутри границ задачи.

**Решения и отложенное.**

- `CallbackData`-классы `ExpenseCallback`, `IncomeCallback`,
  `AccountsCallback`, `ReportsCallback` временно живут в
  `keyboards/menu.py`, а не в файлах роутеров `expense.py`/`income.py`/
  `accounts.py`/`reports.py`, потому что те сейчас пустые заглушки без
  права на хендлеры (граница задания). Когда подзадачи 13/14 наполнят эти
  роутеры, им может понадобиться более богатый формат `callback_data`
  (`<scope>:<action>:<id>:<page>` с реальными `id`/`page`) — тогда классы,
  видимо, стоит перенести в сами роутеры и сохранить только импорт в
  клавиатуре. Осознанно не решал это сейчас, чтобы не проектировать
  наперёд поведение, которого нет в этой задаче.
- Пагинация (раздел 6.7, «Пагинация клавиатур») не применяется — на этапе
  1 нет списков с более чем 8 элементами ни в одной из построенных
  клавиатур.
- `_reply` в `ErrorMiddleware` и `_prompt` в `UserMiddleware` не пытаются
  восстановить `Message` из `InaccessibleMessage` — если кнопка нажата на
  удалённом сообщении, реакция просто не отправляется в чат (для
  `ErrorMiddleware`) или закрывается только `callback.answer` (для
  `UserMiddleware`); отдельно не обрабатывал, поскольку раздел 6.2 этот
  случай не описывает.

**Вопросы диспетчеру.**

1. Раздел 6.3 («Онбординг»): «`/cancel` посреди онбординга сбрасывает его».
   Раздел 6.2 отдаёт `Command('cancel')` только `common.router`, который
   подключён внутрь `registered` за `UserMiddleware`, а `UserMiddleware`
   пропускает без блокировки только `/start`, `/help` и «шаги онбординга»
   (не `/cancel`). Дословно по таблице 6.2 `start.router` обрабатывает
   только `CommandStart()` и `Command('help')` — без `Command('cancel')`.
   Реализовал строго по таблице: `/cancel` от ещё не зарегистрированного
   пользователя посреди онбординга сейчас получает «Нажмите /start» вместо
   сброса состояния, что расходится с разделом 6.3. Варианты решения:
   (а) добавить `start.router` собственный хендлер `Command('cancel')` со
   `StateFilter(Onboarding)`, обновив таблицу 6.2; (б) пропускать `/cancel`
   через `UserMiddleware` так же, как `/start`/`/help`, и оставить его на
   `common.router`. Сам не выбирал — правка `docs/architecture.md` не
   входит в границы задачи.
2. `tests/integration/bot/test_start.py` — артефакт этапа 0, несовместим с
   новой сигнатурой `handle_start` по конструкции задания (см.
   «Проверка»). Нужно решение: удалить/переписать этот файл в рамках
   подзадачи 15b (тестов бота) или отдельной правкой — сам файл я не
   трогал, поскольку границы задачи это запрещают.
