import uuid
from datetime import datetime, timezone

from sqlalchemy import Index, String, Integer, Text, DateTime, ForeignKey, VARCHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_id_created_at", "user_id", "created_at"),
        Index("ix_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # scrape, crawl, map
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, completed, failed, cancelled
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    completed_pages: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    webhook_url: Mapped[str | None] = mapped_column(VARCHAR(2048))
    webhook_secret: Mapped[str | None] = mapped_column(VARCHAR(255))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", back_populates="jobs")
    results = relationship(
        "JobResult", back_populates="job", cascade="all, delete-orphan"
    )
