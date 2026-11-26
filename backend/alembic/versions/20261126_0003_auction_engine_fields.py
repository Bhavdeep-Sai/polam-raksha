"""Add soft-close configuration, entity versioning, and extended bid revision fields.

Revision ID: 20261126_0003
Revises: 20261126_0002
Create Date: 2026-11-26 12:53:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_0003"
down_revision: str | Sequence[str] | None = "20261126_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auctions",
        sa.Column("min_increment_paise_per_kg", sa.BigInteger(), nullable=False, server_default="50"),
    )
    op.add_column(
        "auctions",
        sa.Column(
            "hard_close_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "auctions",
        sa.Column("soft_close_trigger_seconds", sa.Integer(), nullable=False, server_default="120"),
    )
    op.add_column(
        "auctions",
        sa.Column(
            "soft_close_extension_seconds", sa.Integer(), nullable=False, server_default="120"
        ),
    )
    op.add_column(
        "auctions",
        sa.Column(
            "soft_close_max_extension_seconds", sa.Integer(), nullable=False, server_default="600"
        ),
    )
    op.add_column(
        "auctions",
        sa.Column("soft_close_extended_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "auctions",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.add_column(
        "bid_revisions",
        sa.Column(
            "estimated_collection_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "bid_revisions",
        sa.Column(
            "transport_responsibility",
            sa.String(length=30),
            nullable=False,
            server_default="BUYER_PICKUP",
        ),
    )
    op.add_column(
        "bid_revisions",
        sa.Column(
            "estimated_transport_cost_paise", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "bid_revisions",
        sa.Column(
            "standby_until",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "bid_revisions",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=False,
            server_default="legacy",
        ),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_unique_constraint(
            "uq_bid_idempotency",
            "bid_revisions",
            ["auction_id", "buyer_id", "idempotency_key"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("uq_bid_idempotency", "bid_revisions", type_="unique")

    op.drop_column("bid_revisions", "idempotency_key")
    op.drop_column("bid_revisions", "standby_until")
    op.drop_column("bid_revisions", "estimated_transport_cost_paise")
    op.drop_column("bid_revisions", "transport_responsibility")
    op.drop_column("bid_revisions", "estimated_collection_at")

    op.drop_column("auctions", "version")
    op.drop_column("auctions", "soft_close_extended_seconds")
    op.drop_column("auctions", "soft_close_max_extension_seconds")
    op.drop_column("auctions", "soft_close_extension_seconds")
    op.drop_column("auctions", "soft_close_trigger_seconds")
    op.drop_column("auctions", "hard_close_at")
    op.drop_column("auctions", "min_increment_paise_per_kg")

