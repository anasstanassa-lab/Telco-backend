"""
TelcoPulse - Background Scheduler
Runs the monitoring sweep on a fixed interval using asyncio.
Designed to start on application startup and gracefully cancel on shutdown.
"""

import asyncio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.monitor import run_monitoring_sweep

logger = get_logger(__name__)
settings = get_settings()

_scheduler_task: asyncio.Task | None = None


async def _scheduler_loop() -> None:
    """
    Infinite loop that triggers a full monitoring sweep every MONITOR_INTERVAL_SECONDS.
    Any exception inside a sweep is caught and logged so the loop keeps running.
    """
    logger.info(
        f"🚀 Monitoring scheduler started "
        f"(interval={settings.MONITOR_INTERVAL_SECONDS}s)."
    )
    while True:
        try:
            await run_monitoring_sweep()
        except asyncio.CancelledError:
            raise   # propagate cancellation; don't swallow it
        except Exception as exc:
            logger.error(f"Monitoring sweep failed unexpectedly: {exc}", exc_info=True)

        # Wait for the next cycle; CancelledError interrupts sleep cleanly
        await asyncio.sleep(settings.MONITOR_INTERVAL_SECONDS)


def start_scheduler() -> None:
    """
    Schedule the monitoring loop as a background asyncio Task.
    Should be called once from the FastAPI lifespan startup handler.
    """
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(
            _scheduler_loop(), name="telcopulse-monitor"
        )
        logger.info("Background scheduler task created.")
    else:
        logger.warning("Scheduler already running; ignoring duplicate start request.")


def stop_scheduler() -> None:
    """
    Cancel the background monitoring task.
    Should be called from the FastAPI lifespan shutdown handler.
    """
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("Background scheduler task cancelled.")
    _scheduler_task = None
