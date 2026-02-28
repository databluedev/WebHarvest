"""add data_queries table

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_queries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column(
            "query_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_taken", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="success",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_queries_user_id_created_at",
        "data_queries",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_data_queries_platform_operation",
        "data_queries",
        ["platform", "operation"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_queries_platform_operation", table_name="data_queries"
    )
    op.drop_index(
        "ix_data_queries_user_id_created_at", table_name="data_queries"
    )
    op.drop_table("data_queries")
