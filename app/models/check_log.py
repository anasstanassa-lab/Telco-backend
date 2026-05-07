"""
TelcoPulse - CheckLog Model
Immutable audit record of every individual probe sent to a monitored target.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.target import TargetStatus


class CheckLog(Base):
    """
    A single probe result for a Target.

    Columns
    -------
    id          : UUID primary key
    target_id   : FK → targets.id  (cascade delete)
    status      : Result of this probe (UP | DOWN)
    latency_ms  : Round-trip response time in milliseconds (null on error)
    error_msg   : Optional error detail when status is DOWN
    checked_at  : UTC timestamp of the probe
    """

    __tablename__ = "check_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    target_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[TargetStatus] = mapped_column(
        SAEnum(TargetStatus, name="target_status"),
        nullable=False,
    )
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    target: Mapped["Target"] = relationship(   # noqa: F821
        "Target", back_populates="logs"
    )

    def __repr__(self) -> str:
        return (
            f"<CheckLog id={self.id} target_id={self.target_id} "
            f"status={self.status} latency={self.latency_ms}ms>"
        )
