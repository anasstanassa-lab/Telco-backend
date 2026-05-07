"""
TelcoPulse - Target Service
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.target import Target, TargetStatus
from app.models.check_log import CheckLog
from app.schemas.target import TargetCreate
from app.services.monitor import check_target  # Added import

logger = get_logger(__name__)


def _normalise_url(url: str) -> str:
    return str(url).rstrip("/")


async def create_target(session: AsyncSession, payload: TargetCreate) -> Target:
    url = _normalise_url(str(payload.url))

    existing = await session.execute(select(Target).where(Target.url == url))
    if existing.scalar_one_or_none():
        raise ValueError(f"A target with URL '{url}' already exists.")

    target = Target(
        url=url,
        name=payload.name.strip(),
        status=TargetStatus.UNKNOWN,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)

    logger.info(f"New target created: [{target.name}] {target.url} (id={target.id})")

    # ✅ Fire an immediate check so frontend gets real status right away
    asyncio.create_task(check_target(target))

    return target


async def list_targets(session: AsyncSession) -> list[dict]:
    """Return all targets with uptime_percentage and history computed."""
    result = await session.execute(
        select(Target).order_by(Target.created_at.desc())
    )
    targets = list(result.scalars().all())

    enriched = []
    for target in targets:
        # ── Uptime (last 30 days) ─────────────────────────────────────────
        since_30d = datetime.now(timezone.utc) - timedelta(days=30)

        total_result = await session.execute(
            select(func.count())
            .where(CheckLog.target_id == target.id)
            .where(CheckLog.checked_at >= since_30d)
        )
        total = total_result.scalar_one()

        up_result = await session.execute(
            select(func.count())
            .where(CheckLog.target_id == target.id)
            .where(CheckLog.checked_at >= since_30d)
            .where(CheckLog.status == TargetStatus.UP)
        )
        up_count = up_result.scalar_one()

        uptime_pct = round((up_count / total) * 100, 2) if total > 0 else 0.0

        # ── History (last 7 check latencies) ─────────────────────────────
        history_result = await session.execute(
            select(CheckLog.latency_ms)
            .where(CheckLog.target_id == target.id)
            .order_by(CheckLog.checked_at.desc())
            .limit(7)
        )
        # Reverse so oldest → newest (left to right on chart)
        history = list(reversed([row[0] for row in history_result.all()]))

        enriched.append({
            "id": target.id,
            "url": target.url,
            "name": target.name,
            "status": target.status,
            "last_latency_ms": target.last_latency_ms,
            "last_checked_at": target.last_checked_at,
            "created_at": target.created_at,
            "uptime_percentage": uptime_pct,
            "history": history,
        })

    return enriched


async def get_target(session: AsyncSession, target_id: str) -> Optional[Target]:
    result = await session.execute(select(Target).where(Target.id == target_id))
    return result.scalar_one_or_none()


async def delete_target(session: AsyncSession, target_id: str) -> bool:
    result = await session.execute(
        delete(Target).where(Target.id == target_id)
    )
    await session.commit()
    deleted = result.rowcount > 0
    if deleted:
        logger.info(f"Target {target_id} deleted.")
    return deleted


async def get_target_logs(
    session: AsyncSession,
    target_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[CheckLog]]:
    total_result = await session.execute(
        select(func.count()).where(CheckLog.target_id == target_id)
    )
    total = total_result.scalar_one()

    logs_result = await session.execute(
        select(CheckLog)
        .where(CheckLog.target_id == target_id)
        .order_by(CheckLog.checked_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return total, list(logs_result.scalars().all())


async def get_uptime_stats(
    session: AsyncSession,
    target_id: str,
    period_hours: int = 24,
) -> dict:
    target = await get_target(session, target_id)
    if target is None:
        return {}

    since = datetime.now(timezone.utc) - timedelta(hours=period_hours)

    total_result = await session.execute(
        select(func.count())
        .where(CheckLog.target_id == target_id)
        .where(CheckLog.checked_at >= since)
    )
    total = total_result.scalar_one()

    up_result = await session.execute(
        select(func.count())
        .where(CheckLog.target_id == target_id)
        .where(CheckLog.checked_at >= since)
        .where(CheckLog.status == TargetStatus.UP)
    )
    up_count = up_result.scalar_one()

    uptime_pct = round((up_count / total) * 100, 2) if total > 0 else 0.0

    return {
        "target_id": target.id,
        "url": target.url,
        "name": target.name,
        "uptime_percentage": uptime_pct,
        "total_checks": total,
        "successful_checks": up_count,
        "period_hours": period_hours,
    }