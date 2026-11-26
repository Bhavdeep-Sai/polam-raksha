"""Add IVR session persistence, draft state, provider, and webhook replay fields.

Revision ID: 20261126_0005
Revises: 20261126_0004
Create Date: 2026-11-26 13:12:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0005"
down_revision: str | Sequence[str] | None = "20261126_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "ivr_sessions",
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="BROWSER_SIMULATOR"),
    )
    op.add_column(
        "ivr_sessions",
        sa.Column("external_call_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "ivr_sessions",
        sa.Column("last_webhook_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "ivr_sessions",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ivr_sessions",
        sa.Column("draft_json", JSON_TYPE, nullable=False, server_default="{}"),
    )
    op.add_column(
        "ivr_sessions",
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "ivr_sessions",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ivr_sessions_external_call_id",
        "ivr_sessions",
        ["external_call_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ivr_sessions_external_call_id", table_name="ivr_sessions")
    op.drop_column("ivr_sessions", "expires_at")
    op.drop_column("ivr_sessions", "last_activity_at")
    op.drop_column("ivr_sessions", "draft_json")
    op.drop_column("ivr_sessions", "retry_count")
    op.drop_column("ivr_sessions", "last_webhook_id")
    op.drop_column("ivr_sessions", "external_call_id")
    op.drop_column("ivr_sessions", "provider")

