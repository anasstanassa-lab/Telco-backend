"""
TelcoPulse - Target Schemas
Pydantic models for API request validation and response serialisation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator, ConfigDict


# ── Request schemas ───────────────────────────────────────────────────────────

class TargetCreate(BaseModel):
    """Payload accepted when adding a new monitored target."""

    url: HttpUrl
    name: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        if len(v) > 255:
            raise ValueError("name must be ≤ 255 characters")
        return v

    @field_validator("url", mode="before")
    @classmethod
    def url_must_have_scheme(cls, v):
        """Ensure the URL has a valid HTTP/HTTPS scheme."""
        url_str = str(v)
        if not url_str.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


# ── Response schemas ──────────────────────────────────────────────────────────

class TargetResponse(BaseModel):
    """Single target representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    name: str
    status: str
    last_latency_ms: Optional[float]
    last_checked_at: Optional[datetime]
    created_at: datetime


class TargetListResponse(BaseModel):
    """Paginated list of targets."""

    total: int
    items: list[TargetResponse]


class UptimeResponse(BaseModel):
    """Uptime statistics for a single target."""

    target_id: str
    url: str
    name: str
    uptime_percentage: float
    total_checks: int
    successful_checks: int
    period_hours: int
