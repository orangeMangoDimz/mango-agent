"""Attachment cleanup and events.

Revision ID: a4f332540062
Revises: 9b7f0e6ebec2
Create Date: 2026-07-12 20:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4f332540062"
down_revision: str | None = "9b7f0e6ebec2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachment_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("attachment_id", sa.UUID(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("bucket_name", sa.Text(), nullable=False),
        sa.Column("storage_provider", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_attachment_events_status", "status"),
        sa.Index("ix_attachment_events_created_at", "created_at"),
        sa.Index("ix_attachment_events_object_key", "object_key"),
    )

    op.create_index(
        "ix_attachments_lifecycle_status",
        "attachments",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_attachments_expires_at",
        "attachments",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_attachments_expires_at", table_name="attachments")
    op.drop_index("ix_attachments_lifecycle_status", table_name="attachments")
    op.drop_table("attachment_events")
