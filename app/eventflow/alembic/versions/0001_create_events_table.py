"""create events table

Revision ID: 0001
Revises:
Create Date: 2026-11-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_type", sa.String(length=100), nullable=False),
        sa.Column("data", json_type, nullable=False),
        sa.Column("task_context", json_type, nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_events_workflow_type", "events", ["workflow_type"])
    op.create_index("ix_events_status", "events", ["status"])


def downgrade() -> None:
    op.drop_index("ix_events_status", table_name="events")
    op.drop_index("ix_events_workflow_type", table_name="events")
    op.drop_table("events")
