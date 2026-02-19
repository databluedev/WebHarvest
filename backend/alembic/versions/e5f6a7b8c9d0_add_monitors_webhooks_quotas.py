"""add monitors, webhook deliveries, and usage quotas tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: str = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Webhook deliveries
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("request_headers", postgresql.JSONB),
        sa.Column("status_code", sa.Integer),
        sa.Column("response_body", sa.Text),
        sa.Column("response_headers", postgresql.JSONB),
        sa.Column("response_time_ms", sa.Integer),
        sa.Column("success", sa.Boolean, default=False),
        sa.Column("attempt", sa.Integer, default=1),
        sa.Column("max_attempts", sa.Integer, default=3),
        sa.Column("error", sa.Text),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Monitors
    op.create_table(
        "monitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("check_interval_minutes", sa.Integer, default=60),
        sa.Column("css_selector", sa.Text),
        sa.Column("notify_on", sa.String(50), default="any_change"),
        sa.Column("keywords", postgresql.JSONB),
        sa.Column("threshold", sa.Float, default=0.05),
        sa.Column("webhook_url", sa.Text),
        sa.Column("webhook_secret", sa.String(255)),
        sa.Column("headers", postgresql.JSONB),
        sa.Column("cookies", postgresql.JSONB),
        sa.Column("only_main_content", sa.Boolean, default=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True)),
        sa.Column("last_change_at", sa.DateTime(timezone=True)),
        sa.Column("last_status_code", sa.Integer),
        sa.Column("last_content_hash", sa.String(64)),
        sa.Column("last_content", sa.Text),
        sa.Column("total_checks", sa.Integer, default=0),
        sa.Column("total_changes", sa.Integer, default=0),
        sa.Column("next_check_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Monitor checks
    op.create_table(
        "monitor_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status_code", sa.Integer, default=0),
        sa.Column("content_hash", sa.String(64), default=""),
        sa.Column("has_changed", sa.Boolean, default=False),
        sa.Column("change_detail", postgresql.JSONB),
        sa.Column("word_count", sa.Integer, default=0),
        sa.Column("response_time_ms", sa.Integer, default=0),
    )

    # Usage quotas
    op.create_table(
        "usage_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("scrape_limit", sa.Integer, default=10000),
        sa.Column("crawl_limit", sa.Integer, default=1000),
        sa.Column("extract_limit", sa.Integer, default=5000),
        sa.Column("search_limit", sa.Integer, default=2000),
        sa.Column("map_limit", sa.Integer, default=5000),
        sa.Column("batch_limit", sa.Integer, default=5000),
        sa.Column("monitor_limit", sa.Integer, default=100),
        sa.Column("scrape_used", sa.Integer, default=0),
        sa.Column("crawl_used", sa.Integer, default=0),
        sa.Column("extract_used", sa.Integer, default=0),
        sa.Column("search_used", sa.Integer, default=0),
        sa.Column("map_used", sa.Integer, default=0),
        sa.Column("batch_used", sa.Integer, default=0),
        sa.Column("monitor_used", sa.Integer, default=0),
        sa.Column("total_pages_scraped", sa.BigInteger, default=0),
        sa.Column("total_bytes_processed", sa.BigInteger, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "period", name="uq_user_period"),
    )


def downgrade() -> None:
    op.drop_table("monitor_checks")
    op.drop_table("monitors")
    op.drop_table("webhook_deliveries")
    op.drop_table("usage_quotas")
