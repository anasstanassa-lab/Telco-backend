"""
TelcoPulse - CheckLog Schemas
Pydantic models for check log API responses.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CheckLogResponse(BaseModel):
    """Single check log entry representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    target_id: str
    status: str
    latency_ms: Optional[float]
    error_msg: Optional[str]
    checked_at: datetime


class CheckLogListResponse(BaseModel):
    """Paginated list of check logs."""

    total: int
    items: List[CheckLogResponse]