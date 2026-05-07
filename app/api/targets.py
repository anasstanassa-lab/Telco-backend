"""
TelcoPulse - Targets API Router
Handles CRUD operations for monitored targets and exposes log / uptime endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas.target import TargetCreate, TargetResponse, TargetListResponse, UptimeResponse
from app.schemas.check_log import CheckLogListResponse, CheckLogResponse
from app.services import target_service

router = APIRouter(prefix="/api/targets", tags=["Targets"])


# ── List all targets ──────────────────────────────────────────────────────────

@router.get("", response_model=TargetListResponse, summary="List all monitored targets")
async def list_targets(db: AsyncSession = Depends(get_db)):
    """
    Returns every target currently registered in the monitoring system,
    ordered by creation date (newest first).
    """
    targets = await target_service.list_targets(db)
    return TargetListResponse(
        total=len(targets),
        items=[TargetResponse.model_validate(t) for t in targets],
    )


# ── Add a new target ──────────────────────────────────────────────────────────

@router.post("", response_model=TargetResponse, status_code=201, summary="Add a new target")
async def create_target(payload: TargetCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new URL / server for continuous monitoring.

    - **url**: Must be a valid http:// or https:// URL
    - **name**: Human-friendly label (max 255 chars)

    Returns HTTP 409 if a target with the same URL already exists.
    """
    try:
        target = await target_service.create_target(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return TargetResponse.model_validate(target)


# ── Delete a target ───────────────────────────────────────────────────────────

@router.delete("/{target_id}", status_code=204, summary="Delete a target")
async def delete_target(target_id: str, db: AsyncSession = Depends(get_db)):
    """
    Permanently remove a target and all its associated check logs.
    Returns HTTP 404 if the target does not exist.
    """
    deleted = await target_service.delete_target(db, target_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Target not found.")


# ── Get historical logs ───────────────────────────────────────────────────────

@router.get(
    "/{target_id}/logs",
    response_model=CheckLogListResponse,
    summary="Get historical probe logs for a target",
)
async def get_target_logs(
    target_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Result offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the probe history for a target, sorted by most recent first.

    Use `limit` and `offset` for pagination.
    Returns HTTP 404 if the target does not exist.
    """
    target = await target_service.get_target(db, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found.")

    total, logs = await target_service.get_target_logs(db, target_id, limit, offset)
    return CheckLogListResponse(
        target_id=target_id,
        total=total,
        items=[CheckLogResponse.model_validate(log) for log in logs],
    )


# ── Uptime statistics ─────────────────────────────────────────────────────────

@router.get(
    "/{target_id}/uptime",
    response_model=UptimeResponse,
    summary="Get uptime percentage for a target",
)
async def get_uptime(
    target_id: str,
    hours: int = Query(default=24, ge=1, le=720, description="Lookback window in hours"),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculates the percentage of successful checks over the last N hours
    (default 24 h, max 720 h / 30 days).
    Returns HTTP 404 if the target does not exist.
    """
    stats = await target_service.get_uptime_stats(db, target_id, period_hours=hours)
    if not stats:
        raise HTTPException(status_code=404, detail="Target not found.")
    return UptimeResponse(**stats)
