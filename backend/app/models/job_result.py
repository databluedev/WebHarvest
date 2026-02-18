import uuid
from datetime import datetime, timezone

from sqlalchemy import Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobResult(Base):
    __tablename__ = "job_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str | None] = mapped_column(Text)
    html: Mapped[str | None] = mapped_column(Text)
    links: Mapped[dict | None] = mapped_column(JSONB)
    extract: Mapped[dict | None] = mapped_column(JSONB)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    screenshot_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    job = relationship("Job", back_populates="results")
