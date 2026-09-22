"""Запуск APScheduler — точка входа процесса `worker`.

Раздел `docs/architecture.md`, 1.2 «Развёртываемые процессы», 9.1 «Выбор
планировщика», 13 «Этап 0»: этап 0 не регистрирует ни одной job — только
каркас, который стартует вместе с остальным стеком `docker-compose`.

`python -m finplan.entrypoints.worker.main` запускает `main()`. При
`SCHEDULER_ENABLED=false` процесс логирует это и завершается кодом 0, не
поднимая планировщик.
"""

from __future__ import annotations

import asyncio
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from finplan.config import get_settings
from finplan.logging import configure_logging, get_logger


async def main() -> None:
    """Настраивает логирование и запускает планировщик до сигнала завершения."""
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)
    logger.info("process.starting", service="worker", scheduler_enabled=settings.scheduler_enabled)

    if not settings.scheduler_enabled:
        logger.info("worker.scheduler_disabled", detail="SCHEDULER_ENABLED=false")
        return

    scheduler = AsyncIOScheduler()
    logger.info("worker.scheduler_starting", jobs=[job.id for job in scheduler.get_jobs()])
    scheduler.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown()
        logger.info("process.stopped", service="worker")


if __name__ == "__main__":
    asyncio.run(main())
