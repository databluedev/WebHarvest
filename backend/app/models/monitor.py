"""URL change monitoring models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Monitor(Base):
    """Tracks a URL for content changes."""

    __tablename__ = "monitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    css_selector: Mapped[str | None] = mapped_column(Text)
    notify_on: Mapped[str] = mapped_column(String(50), default="any_change")
    keywords: Mapped[list | None] = mapped_column(JSONB)
    threshold: Mapped[float] = mapped_column(Float, default=0.05)

    # Auth/config
    webhook_url: Mapped[str | None] = mapped_column(Text)
    webhook_secret: Mapped[str | None] = mapped_column(String(255))
    headers: Mapped[dict | None] = mapped_column(JSONB)
    cookies: Mapped[dict | None] = mapped_column(JSONB)
    only_main_content: Mapped[bool] = mapped_column(Boolean, default=False)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_content_hash: Mapped[str | None] = mapped_column(String(64))
    last_content: Mapped[str | None] = mapped_column(Text)
    total_checks: Mapped[int] = mapped_column(Integer, default=0)
    total_changes: Mapped[int] = mapped_column(Integer, default=0)
    next_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", backref="monitors")
    checks = relationship(
        "MonitorCheck",
        back_populates="monitor",
        cascade="all, delete-orphan",
        order_by="MonitorCheck.checked_at.desc()",
    )


class MonitorCheck(Base):
    """Individual check result for a monitor."""

    __tablename__ = "monitor_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    monitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status_code: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    has_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    change_detail: Mapped[dict | None] = mapped_column(JSONB)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    monitor = relationship("Monitor", back_populates="checks")
