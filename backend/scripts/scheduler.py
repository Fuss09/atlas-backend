"""
Atlas - Scheduler
=================
Déclenche le cycle nocturne chaque jour à heure fixe. Conteneur DÉDIÉ
(hors processus web) — l'API reste légère.
"""
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from scripts.run_cycle import run_cycle

logger = get_logger(__name__)


async def _job() -> None:
    logger.info("Scheduler triggering nightly cycle")
    await run_cycle("real")


async def main() -> None:
    configure_logging()
    settings = get_settings()

    if not settings.scheduler_enabled:
        logger.warning("Scheduler disabled — idling")
        while True:
            await asyncio.sleep(3600)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(_job, CronTrigger(hour=settings.scheduler_hour, minute=0),
                      id="nightly_cycle", max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("Scheduler started", hour_utc=settings.scheduler_hour)
    for job in scheduler.get_jobs():
        logger.info("Job scheduled", id=job.id, next_run=str(job.next_run_time))

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
