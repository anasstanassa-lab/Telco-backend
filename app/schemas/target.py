"""
TelcoPulse - Target Schemas
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, field_validator, ConfigDict


class TargetCreate(BaseModel):
    url: str
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
        url_str = str(v)
        if not url_str.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    name: str
    status: str
    last_latency_ms: Optional[float] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    uptime_percentage: Optional[float] = None
    history: List[Optional[float]] = []


class TargetListResponse(BaseModel):
    total: int
    items: list[TargetResponse]


class UptimeResponse(BaseModel):
    target_id: str
    url: str
    name: str
    uptime_percentage: float
    total_checks: int
    successful_checks: int
    period_hours: int
