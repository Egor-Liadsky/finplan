"""Запуск aiogram `Dispatcher` — точка входа процесса `bot`.

Раздел `docs/architecture.md`, 1.2 «Развёртываемые процессы», 1.3 «Бот и
API — разные процессы», 10.1 «Переменные окружения», 10.5 «Режим бота».

Этап 0 поддерживает только `TELEGRAM_MODE=polling`; в режиме `webhook`
процесс завершается понятным сообщением — приём вебхука появится в `api`
вместе с очередью Redis (раздел 1.3). Хранилище FSM — `MemoryStorage`, если
`REDIS_URL` не задан, иначе `RedisStorage` (раздел 10.1).

`bot` и `dp` — модульные объекты: создание не обращается к сети (клиент
Bot API и подключение к Redis лениво устанавливаются при первом вызове), а
`python -m finplan.entrypoints.bot.main` запускает `main()`.
"""

from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from finplan.config import get_settings
from finplan.entrypoints.bot.routers.start import router as start_router
from finplan.logging import configure_logging, get_logger

settings = get_settings()

bot = Bot(token=settings.telegram.bot_token.get_secret_value())

storage = RedisStorage.from_url(settings.redis_url) if settings.redis_url else MemoryStorage()

dp = Dispatcher(storage=storage)
dp.include_router(start_router)


async def main() -> None:
    """Настраивает логирование и запускает `Dispatcher` в выбранном режиме."""
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

    logger.info(
        "process.starting",
        service="bot",
        mode=settings.telegram.mode,
        storage=type(storage).__name__,
    )
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("process.stopped", service="bot")


if __name__ == "__main__":
    asyncio.run(main())
