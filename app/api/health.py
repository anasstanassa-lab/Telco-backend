"""
TelcoPulse - Health API Router
Provides liveness and readiness probes for the application.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Health check")
async def health_check():
    """Simple liveness probe that returns 200 OK if the service is running."""
    return {"status": "healthy"}