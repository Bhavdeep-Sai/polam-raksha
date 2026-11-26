"""Add listing lifecycle states, deadline schedule columns, and assisted consent method.

Revision ID: 20261126_0002
Revises: 20261126_0001
Create Date: 2026-11-26 12:45:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0002"
down_revision: str | Sequence[str] | None = "20261126_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE listing_status ADD VALUE IF NOT EXISTS 'PARTIALLY_ALLOCATED'")
        op.execute("ALTER TYPE listing_status ADD VALUE IF NOT EXISTS 'FULLY_ALLOCATED'")

    op.add_column(
        "assisted_access_relationships",
        sa.Column(
            "consent_method",
            sa.String(length=40),
            nullable=False,
            server_default="IN_PERSON_VERBAL",
        ),
    )

    op.add_column(
        "produce_listings",
        sa.Column("quality_grade", sa.String(length=20), nullable=False, server_default="GRADE_A"),
    )
    op.add_column(
        "produce_listings",
        sa.Column("photo_urls_json", JSON_TYPE, nullable=False, server_default="[]"),
    )
    op.add_column(
        "produce_listings",
        sa.Column(
            "transport_responsibility",
            sa.String(length=30),
            nullable=False,
            server_default="BUYER_PICKUP",
        ),
    )
    op.add_column(
        "produce_listings",
        sa.Column(
            "auto_allocate_approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "produce_listings",
        sa.Column(
            "urgency_option",
            sa.String(length=20),
            nullable=False,
            server_default="WITHIN_24H",
        ),
    )
    op.add_column(
        "produce_listings",
        sa.Column(
            "is_direct_offer_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "produce_listings",
        sa.Column("bidding_initial_close_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "produce_listings",
        sa.Column("bidding_hard_close_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "produce_listings",
        sa.Column("farmer_approval_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "produce_listings",
        sa.Column("buyer_confirmation_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "produce_listings",
        sa.Column("recovery_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("produce_listings", "recovery_deadline_at")
    op.drop_column("produce_listings", "buyer_confirmation_deadline_at")
    op.drop_column("produce_listings", "farmer_approval_deadline_at")
    op.drop_column("produce_listings", "bidding_hard_close_at")
    op.drop_column("produce_listings", "bidding_initial_close_at")
    op.drop_column("produce_listings", "is_direct_offer_mode")
    op.drop_column("produce_listings", "urgency_option")
    op.drop_column("produce_listings", "auto_allocate_approved")
    op.drop_column("produce_listings", "transport_responsibility")
    op.drop_column("produce_listings", "photo_urls_json")
    op.drop_column("produce_listings", "quality_grade")
    op.drop_column("assisted_access_relationships", "consent_method")

