"""add webhook fields to jobs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-19 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("webhook_url", sa.VARCHAR(2048), nullable=True))
    op.add_column("jobs", sa.Column("webhook_secret", sa.VARCHAR(255), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "webhook_secret")
    op.drop_column("jobs", "webhook_url")
