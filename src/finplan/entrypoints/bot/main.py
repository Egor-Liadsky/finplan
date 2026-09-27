"""Сборка и запуск aiogram `Dispatcher` — точка входа процесса `bot`.

Раздел `docs/architecture.md`, 1.2 «Развёртываемые процессы», 1.3 «Бот и
API — разные процессы», 6.2 «Разбиение на роутеры aiogram», 10.1
«Переменные окружения», 10.5 «Режим бота».

Этап 1 поддерживает только `TELEGRAM_MODE=polling`; в режиме `webhook`
процесс завершается понятным сообщением — приём вебхука появится в `api`
вместе с очередью Redis (раздел 1.3). Хранилище FSM — `MemoryStorage`, если
`REDIS_URL` не задан, иначе `RedisStorage` (раздел 6.4, 10.1).

Модульных объектов `bot` и `dp` здесь нет: `create_dispatcher` — чистая
фабрика, которую интеграционные тесты подзадачи 15b вызывают напрямую со
своим `Container` и `MemoryStorage`, не создавая ни настоящего `Bot`, ни
подключения к БД. `python -m finplan.entrypoints.bot.main` запускает
`main()`, которая уже строит настоящие объекты и обращается к сети и БД.
"""

from __future__ import annotations

import asyncio
import sys

from aiogram import Dispatcher, Router
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from finplan.config import Settings, get_settings
from finplan.container import Container, build_container
from finplan.entrypoints.bot.middlewares.errors import ErrorMiddleware
from finplan.entrypoints.bot.middlewares.logging import LoggingMiddleware
from finplan.entrypoints.bot.middlewares.user import UserMiddleware
from finplan.entrypoints.bot.routers.accounts import router as accounts_router
from finplan.entrypoints.bot.routers.common import router as common_router
from finplan.entrypoints.bot.routers.expense import router as expense_router
from finplan.entrypoints.bot.routers.fallback import router as fallback_router
from finplan.entrypoints.bot.routers.income import router as income_router
from finplan.entrypoints.bot.routers.quick import router as quick_router
from finplan.entrypoints.bot.routers.reports import router as reports_router
from finplan.entrypoints.bot.routers.start import router as start_router
from finplan.entrypoints.bot.routers.undo import router as undo_router
from finplan.infrastructure.telegram.bot import create_bot
from finplan.logging import configure_logging, get_logger

#: Раздел 6.1, таблица команд, описания скопированы дословно — подмножество,
#: зарегистрированное `set_my_commands` на этапе 1 (раздел 2.2, «Меню по
#: этапам»: только команды с уже существующим обработчиком).
_BOT_COMMANDS: tuple[BotCommand, ...] = (
    BotCommand(command="start", description="Регистрация или привязка, онбординг"),
    BotCommand(command="help", description="Справка, в том числе синтаксис быстрого ввода"),
    BotCommand(command="menu", description="Показать главное меню"),
    BotCommand(command="expense", description="Сразу в диалог добавления расхода"),
    BotCommand(command="income", description="Сразу в диалог добавления дохода"),
    BotCommand(command="balance", description="Остатки по всем счетам и итог в базовой валюте"),
    BotCommand(command="today", description="Сводка расходов и доходов за сегодня"),
    BotCommand(command="month", description="Сводка расходов и доходов за текущий месяц"),
    BotCommand(command="undo", description="Сторнировать последнюю операцию, введённую в боте"),
    BotCommand(command="cancel", description="Выйти из любого диалога"),
)


def create_dispatcher(container: Container, storage: BaseStorage) -> Dispatcher:
    """Собирает `Dispatcher`: middleware и роутеры этапа 1 в порядке раздела 6.2.

    `start.router` подключается напрямую к диспетчеру — онбордингу
    пользователь из базы не нужен (абзац «Регистрация»). Остальные роутеры
    этапа 1 подключаются в порядке таблицы 6.2 внутрь родительского роутера
    `registered`, на котором `UserMiddleware` висит внешним middleware для
    событий `message` и `callback_query` — тех же двух типов апдейтов, для
    которых нужен `User` из базы. Контейнер кладётся в `workflow_data` под
    ключом `container`, поэтому доступен любому хендлеру и middleware
    аргументом с этим именем, без явной передачи по цепочке.
    """
    dp = Dispatcher(storage=storage, container=container)

    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(ErrorMiddleware())

    dp.include_router(start_router)

    registered = Router(name="registered")
    registered.message.outer_middleware(UserMiddleware())
    registered.callback_query.outer_middleware(UserMiddleware())
    for sub_router in (
        common_router,
        undo_router,
        expense_router,
        income_router,
        accounts_router,
        reports_router,
        quick_router,
        fallback_router,
    ):
        registered.include_router(sub_router)
    dp.include_router(registered)

    return dp


async def main() -> None:
    """Настраивает логирование, поднимает контейнер и бот, запускает polling."""
    settings: Settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    if settings.telegram.mode == "webhook":
        logger.error(
            "bot.webhook_not_supported",
            detail=(
                "режим webhook появится вместе с приёмом вебхука в api "
                "(docs/architecture.md, раздел 1.3); используйте "
                "TELEGRAM_MODE=polling"
            ),
        )
        sys.exit(1)

    container = build_container(settings)
    bot = create_bot(settings.telegram)
    storage: BaseStorage = (
        RedisStorage.from_url(settings.redis_url) if settings.redis_url else MemoryStorage()
    )
    dp = create_dispatcher(container, storage)

    logger.info(
        "process.starting",
        service="bot",
        mode=settings.telegram.mode,
        storage=type(storage).__name__,
    )
    try:
        await bot.set_my_commands(list(_BOT_COMMANDS))
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await container.aclose()
        logger.info("process.stopped", service="bot")


if __name__ == "__main__":
    asyncio.run(main())
