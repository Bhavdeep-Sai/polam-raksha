"""Add buyer verification, notification deduplication/status, and dispute cases.

Revision ID: 20261126_0007
Revises: 20261126_0006
Create Date: 2026-11-26 13:27:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_0007"
down_revision: str | Sequence[str] | None = "20261126_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "buyer_profiles",
        sa.Column(
            "verification_status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column(
        "buyer_profiles",
        sa.Column("is_restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column(
        "notifications",
        sa.Column("event_id", sa.String(length=120), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "notifications",
        sa.Column("event_type", sa.String(length=80), nullable=False, server_default="GENERAL"),
    )
    op.add_column(
        "notifications",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DELIVERED"),
    )
    op.add_column(
        "notifications",
        sa.Column("provider_message", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "notifications",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.create_unique_constraint(
            "uq_notification_user_event_channel",
            ["user_id", "event_id", "channel"],
        )

    op.create_table(
        "dispute_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("raised_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raised_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dispute_cases_status", "dispute_cases", ["status"])


def downgrade() -> None:
    op.drop_index("ix_dispute_cases_status", table_name="dispute_cases")
    op.drop_table("dispute_cases")
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint("uq_notification_user_event_channel", type_="unique")
    op.drop_column("notifications", "acknowledged_at")
    op.drop_column("notifications", "delivered_at")
    op.drop_column("notifications", "metadata_json")
    op.drop_column("notifications", "provider_message")
    op.drop_column("notifications", "status")
    op.drop_column("notifications", "event_type")
    op.drop_column("notifications", "event_id")
    op.drop_column("buyer_profiles", "is_restricted")
    op.drop_column("buyer_profiles", "verification_status")
