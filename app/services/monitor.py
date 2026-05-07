"""
TelcoPulse - Monitor Service
Performs HTTP health checks against targets, stores results, and emits alerts.
Designed to be called from both the background scheduler and tests.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import AsyncSessionLocal
from app.models.target import Target, TargetStatus
from app.models.check_log import CheckLog

logger = get_logger(__name__)
settings = get_settings()


# ── Low-level probe ───────────────────────────────────────────────────────────

async def _probe_url(url: str, client: httpx.AsyncClient) -> tuple[TargetStatus, Optional[float], Optional[str]]:
    """
    Send a single GET request and measure latency.

    Returns
    -------
    (status, latency_ms, error_message)
    """
    start = time.monotonic()
    try:
        response = await client.get(url, follow_redirects=True)
        latency_ms = (time.monotonic() - start) * 1000

        if response.status_code < 500:
            return TargetStatus.UP, round(latency_ms, 2), None
        else:
            return TargetStatus.DOWN, round(latency_ms, 2), f"HTTP {response.status_code}"

    except httpx.TimeoutException:
        latency_ms = (time.monotonic() - start) * 1000
        return TargetStatus.DOWN, round(latency_ms, 2), "Request timed out"

    except httpx.RequestError as exc:
        return TargetStatus.DOWN, None, str(exc)


async def _probe_with_retry(url: str, client: httpx.AsyncClient) -> tuple[TargetStatus, Optional[float], Optional[str]]:
    """
    Probe a URL with up to HTTP_MAX_RETRIES attempts on transient failures.
    """
    last_status, last_latency, last_error = TargetStatus.DOWN, None, "Unknown error"

    for attempt in range(settings.HTTP_MAX_RETRIES + 1):
        last_status, last_latency, last_error = await _probe_url(url, client)
        if last_status == TargetStatus.UP:
            return last_status, last_latency, last_error
        if attempt < settings.HTTP_MAX_RETRIES:
            logger.debug(f"Retry {attempt + 1}/{settings.HTTP_MAX_RETRIES} for {url}: {last_error}")
            await asyncio.sleep(settings.HTTP_RETRY_WAIT_SECONDS)

    return last_status, last_latency, last_error


# ── Database operations ───────────────────────────────────────────────────────

async def _save_check_result(
    session: AsyncSession,
    target: Target,
    status: TargetStatus,
    latency_ms: Optional[float],
    error_msg: Optional[str],
) -> None:
    """
    Persist check results:
    1. Insert a new CheckLog row.
    2. Update the parent Target (status, latency, last_checked_at).
    3. Emit an alert log if status changed.
    """
    now = datetime.now(timezone.utc)
    previous_status = target.status

    # ── Alerting: log status transitions ─────────────────────────────────────
    if previous_status != status and previous_status != TargetStatus.UNKNOWN:
        if status == TargetStatus.DOWN:
            logger.warning(
                f"🔴 ALERT | Target DOWN  | {target.url} "
                f"| error: {error_msg}"
            )
        else:
            logger.info(
                f"🟢 ALERT | Target UP    | {target.url} "
                f"| recovered after being DOWN"
            )

    # ── Write CheckLog ────────────────────────────────────────────────────────
    log_entry = CheckLog(
        target_id=target.id,
        status=status,
        latency_ms=latency_ms,
        error_msg=error_msg,
        checked_at=now,
    )
    session.add(log_entry)

    # ── Update Target ─────────────────────────────────────────────────────────
    target.status = status
    target.last_latency_ms = latency_ms
    target.last_checked_at = now
    session.add(target)

    await session.commit()


# ── Per-target check ──────────────────────────────────────────────────────────

async def check_target(target: Target) -> None:
    """
    Probe a single target and persist the result in its own DB session.
    Safe to call concurrently for multiple targets.
    """
    async with httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": f"TelcoPulse/{settings.APP_VERSION}"},
    ) as client:
        status, latency_ms, error_msg = await _probe_with_retry(target.url, client)

    log_icon = "✅" if status == TargetStatus.UP else "❌"
    logger.info(
        f"{log_icon} Check | {target.url} "
        f"| status={status.value} latency={latency_ms}ms"
    )

    async with AsyncSessionLocal() as session:
        # Re-fetch the target inside this session to avoid detached-instance issues
        result = await session.execute(select(Target).where(Target.id == target.id))
        db_target = result.scalar_one_or_none()
        if db_target is None:
            logger.warning(f"Target {target.id} was deleted before check could be saved.")
            return
        await _save_check_result(session, db_target, status, latency_ms, error_msg)


# ── Full sweep ────────────────────────────────────────────────────────────────

async def run_monitoring_sweep() -> None:
    """
    Fetch all targets and probe them concurrently.
    This is the function invoked by the background scheduler every N seconds.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Target))
        targets: list[Target] = list(result.scalars().all())

    if not targets:
        logger.debug("No targets to monitor.")
        return

    logger.info(f"🔍 Starting monitoring sweep for {len(targets)} target(s).")
    tasks = [check_target(t) for t in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Report any unexpected errors so they don't silently vanish
    for target, outcome in zip(targets, results):
        if isinstance(outcome, Exception):
            logger.error(f"Unhandled error checking {target.url}: {outcome}")

    logger.info("✔ Monitoring sweep complete.")