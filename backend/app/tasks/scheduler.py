from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import structlog

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()


async def example_job():
    """Placeholder periodic job. Replace with your own logic."""
    logger.info("example_job_tick")


def start_scheduler():
    scheduler.add_job(
        example_job,
        IntervalTrigger(minutes=60),
        id="example_job",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)
