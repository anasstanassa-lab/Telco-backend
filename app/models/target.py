"""
TelcoPulse - Target Model
Represents a URL / server endpoint that the system continuously monitors.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base


class TargetStatus(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"   # initial state before first check


class Target(Base):
    """
    A monitored endpoint.

    Columns
    -------
    id              : UUID primary key
    url             : The full URL/IP to probe (e.g. https://example.com)
    name            : Human-friendly label
    status          : Last known status (UP | DOWN | UNKNOWN)
    last_latency_ms : Response time of the most recent successful check (ms)
    last_checked_at : Timestamp of the most recent check attempt
    created_at      : Row creation timestamp
    """

    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TargetStatus] = mapped_column(
        SAEnum(TargetStatus, name="target_status"),
        default=TargetStatus.UNKNOWN,
        nullable=False,
    )
    last_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    logs: Mapped[list["CheckLog"]] = relationship(   # noqa: F821
        "CheckLog",
        back_populates="target",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Target id={self.id} url={self.url} status={self.status}>"
