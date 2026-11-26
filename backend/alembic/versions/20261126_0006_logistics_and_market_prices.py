"""Add location consent, road distance cache, transport economics, and market reference prices.

Revision ID: 20261126_0006
Revises: 20261126_0005
Create Date: 2026-11-26 13:18:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_0006"
down_revision: str | Sequence[str] | None = "20261126_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "farmer_profiles",
        sa.Column("location_consent_given", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "buyer_profiles",
        sa.Column("location_consent_given", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("buyer_profiles", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("buyer_profiles", sa.Column("longitude", sa.Float(), nullable=True))

    op.add_column(
        "transport_quotes",
        sa.Column(
            "distance_kind",
            sa.String(length=30),
            nullable=False,
            server_default="APPROX_STRAIGHT_LINE",
        ),
    )
    op.add_column(
        "transport_quotes",
        sa.Column("estimated_travel_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "transport_quotes",
        sa.Column("fixed_pickup_cost_paise", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "transport_quotes",
        sa.Column("variable_cost_paise", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "transport_quotes",
        sa.Column(
            "transport_responsibility",
            sa.String(length=30),
            nullable=False,
            server_default="BUYER_PICKUP",
        ),
    )
    op.add_column(
        "transport_quotes",
        sa.Column("farmer_paid_cost_paise", sa.BigInteger(), nullable=False, server_default="0"),
    )

    op.create_table(
        "road_distance_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("origin_key", sa.String(length=64), nullable=False),
        sa.Column("dest_key", sa.String(length=64), nullable=False),
        sa.Column("distance_meters", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "distance_meters >= 0", name=op.f("ck_road_distance_cache_cache_distance_non_negative")
        ),
        sa.CheckConstraint(
            "duration_seconds >= 0", name=op.f("ck_road_distance_cache_cache_duration_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_road_distance_cache")),
    )
    op.create_index(
        "ix_road_distance_cache_pair",
        "road_distance_cache",
        ["origin_key", "dest_key"],
        unique=True,
    )

    op.create_table(
        "market_reference_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("commodity_code", sa.String(length=50), nullable=False),
        sa.Column("commodity_name_en", sa.String(length=120), nullable=False),
        sa.Column("commodity_name_te", sa.String(length=120), nullable=False),
        sa.Column("market_name", sa.String(length=150), nullable=False),
        sa.Column("district", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("grade", sa.String(length=40), nullable=False),
        sa.Column("price_type", sa.String(length=20), nullable=False),
        sa.Column("original_unit", sa.String(length=20), nullable=False),
        sa.Column("original_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("normalized_price_paise_per_kg", sa.BigInteger(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(length=60), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "original_price_paise > 0",
            name=op.f("ck_market_reference_prices_market_orig_price_positive"),
        ),
        sa.CheckConstraint(
            "normalized_price_paise_per_kg > 0",
            name=op.f("ck_market_reference_prices_market_norm_price_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_reference_prices")),
    )
    op.create_index(
        "ix_market_prices_commodity_obs",
        "market_reference_prices",
        ["commodity_code", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_prices_commodity_obs", table_name="market_reference_prices")
    op.drop_table("market_reference_prices")
    op.drop_index("ix_road_distance_cache_pair", table_name="road_distance_cache")
    op.drop_table("road_distance_cache")
    op.drop_column("transport_quotes", "farmer_paid_cost_paise")
    op.drop_column("transport_quotes", "transport_responsibility")
    op.drop_column("transport_quotes", "variable_cost_paise")
    op.drop_column("transport_quotes", "fixed_pickup_cost_paise")
    op.drop_column("transport_quotes", "estimated_travel_seconds")
    op.drop_column("transport_quotes", "distance_kind")
    op.drop_column("buyer_profiles", "longitude")
    op.drop_column("buyer_profiles", "latitude")
    op.drop_column("buyer_profiles", "location_consent_given")
    op.drop_column("farmer_profiles", "location_consent_given")

