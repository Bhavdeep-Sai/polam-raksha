"""Add allocation run snapshot, explanations, and farmer approval fields.

Revision ID: 20261126_0004
Revises: 20261126_0003
Create Date: 2026-11-26 13:05:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0004"
down_revision: str | Sequence[str] | None = "20261126_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "allocation_runs",
        sa.Column("algorithm_version", sa.String(length=40), nullable=False, server_default="cp-sat-v1.0"),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("strategy", sa.String(length=30), nullable=False, server_default="REVENUE_FIRST"),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("input_snapshot_json", JSON_TYPE, nullable=False, server_default="{}"),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("explanations_json", JSON_TYPE, nullable=False, server_default="[]"),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("gross_revenue_paise", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("transportation_cost_paise", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "allocation_runs",
        sa.Column(
            "estimated_net_revenue_paise", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "allocation_runs",
        sa.Column(
            "unallocated_quantity_grams", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("execution_time_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "allocation_runs",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("allocation_runs", "approved_at")
    op.drop_column("allocation_runs", "is_approved")
    op.drop_column("allocation_runs", "execution_time_ms")
    op.drop_column("allocation_runs", "unallocated_quantity_grams")
    op.drop_column("allocation_runs", "estimated_net_revenue_paise")
    op.drop_column("allocation_runs", "transportation_cost_paise")
    op.drop_column("allocation_runs", "gross_revenue_paise")
    op.drop_column("allocation_runs", "explanations_json")
    op.drop_column("allocation_runs", "input_snapshot_json")
    op.drop_column("allocation_runs", "strategy")
    op.drop_column("allocation_runs", "algorithm_version")

