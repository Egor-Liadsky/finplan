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

_Заполняет исполнитель. Выше этой строки ничего не меняется._
