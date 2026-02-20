"""Credit/quota system for usage tracking and limits."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    BigInteger,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UsageQuota(Base):
    """Per-user monthly usage tracking and quota enforcement."""

    __tablename__ = "usage_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period: Mapped[str] = mapped_column(
        String(7),
        nullable=False,  # "2026-02" format (YYYY-MM)
    )

    # Credit limits (-1 = unlimited)
    scrape_limit: Mapped[int] = mapped_column(Integer, default=10000)
    crawl_limit: Mapped[int] = mapped_column(Integer, default=1000)
    extract_limit: Mapped[int] = mapped_column(Integer, default=5000)
    search_limit: Mapped[int] = mapped_column(Integer, default=2000)
    map_limit: Mapped[int] = mapped_column(Integer, default=5000)
    batch_limit: Mapped[int] = mapped_column(Integer, default=5000)
    monitor_limit: Mapped[int] = mapped_column(Integer, default=100)

    # Actual usage counters
    scrape_used: Mapped[int] = mapped_column(Integer, default=0)
    crawl_used: Mapped[int] = mapped_column(Integer, default=0)
    extract_used: Mapped[int] = mapped_column(Integer, default=0)
    search_used: Mapped[int] = mapped_column(Integer, default=0)
    map_used: Mapped[int] = mapped_column(Integer, default=0)
    batch_used: Mapped[int] = mapped_column(Integer, default=0)
    monitor_used: Mapped[int] = mapped_column(Integer, default=0)

    # Aggregate stats
    total_pages_scraped: Mapped[int] = mapped_column(BigInteger, default=0)
    total_bytes_processed: Mapped[int] = mapped_column(BigInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (UniqueConstraint("user_id", "period", name="uq_user_period"),)

    # Relationships
    user = relationship("User", backref="usage_quotas")
