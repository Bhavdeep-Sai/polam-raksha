"""Initial normalized PolamRaksha schema.

Revision ID: 20261126_0001
Revises:
Create Date: 2026-11-26 12:30:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=20), nullable=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("preferred_language", sa.String(length=5), nullable=False),
        sa.Column(
            "role",
            sa.Enum("FARMER", "BUYER", "OPERATOR", "ADMIN", name="user_role"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("pin_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_pin_attempts", sa.Integer(), nullable=False),
        sa.Column("pin_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "failed_pin_attempts >= 0", name=op.f("ck_users_failed_pin_attempts_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("phone_number", name=op.f("uq_users_phone_number")),
    )
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "crop_catalog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name_en", sa.String(length=120), nullable=False),
        sa.Column("name_te", sa.String(length=120), nullable=False),
        sa.Column("unit_label_en", sa.String(length=30), nullable=False),
        sa.Column("unit_label_te", sa.String(length=30), nullable=False),
        sa.Column("default_shelf_life_hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "default_shelf_life_hours > 0", name=op.f("ck_crop_catalog_shelf_life_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crop_catalog")),
        sa.UniqueConstraint("code", name=op.f("uq_crop_catalog_code")),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], unique=False)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "farmer_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("village", sa.String(length=120), nullable=False),
        sa.Column("mandal", sa.String(length=120), nullable=False),
        sa.Column("district", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("exact_pickup_address", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("approx_latitude", sa.Float(), nullable=True),
        sa.Column("approx_longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_farmer_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_farmer_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_farmer_profiles_user_id")),
    )

    op.create_table(
        "buyer_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("business_name", sa.String(length=180), nullable=False),
        sa.Column("buyer_type", sa.String(length=60), nullable=False),
        sa.Column("district", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("gstin", sa.String(length=20), nullable=True),
        sa.Column("reliability_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 100",
            name=op.f("ck_buyer_profiles_buyer_reliability_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_buyer_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buyer_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_buyer_profiles_user_id")),
    )

    op.create_table(
        "assisted_access_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=False),
        sa.Column("farmer_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "operator_id != farmer_id",
            name=op.f("ck_assisted_access_relationships_operator_not_self_farmer"),
        ),
        sa.ForeignKeyConstraint(
            ["farmer_id"],
            ["users.id"],
            name=op.f("fk_assisted_access_relationships_farmer_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["users.id"],
            name=op.f("fk_assisted_access_relationships_operator_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assisted_access_relationships")),
        sa.UniqueConstraint("operator_id", "farmer_id", name="uq_operator_farmer"),
    )
    op.create_index(
        "ix_assisted_access_operator_active",
        "assisted_access_relationships",
        ["operator_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "produce_listings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("farmer_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("crop_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "ACTIVE",
                "ALLOCATED",
                "COMPLETED",
                "EXPIRED",
                "CANCELLED",
                name="listing_status",
            ),
            nullable=False,
        ),
        sa.Column("total_quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("available_quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("reserved_quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("collected_quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("floor_price_paise_per_kg", sa.BigInteger(), nullable=False),
        sa.Column("harvested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spoilage_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approx_location_label", sa.String(length=180), nullable=False),
        sa.Column("approx_latitude", sa.Float(), nullable=True),
        sa.Column("approx_longitude", sa.Float(), nullable=True),
        sa.Column("exact_pickup_address", sa.Text(), nullable=False),
        sa.Column("exact_latitude", sa.Float(), nullable=True),
        sa.Column("exact_longitude", sa.Float(), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "total_quantity_grams > 0", name=op.f("ck_produce_listings_total_qty_positive")
        ),
        sa.CheckConstraint(
            "available_quantity_grams >= 0",
            name=op.f("ck_produce_listings_available_qty_non_negative"),
        ),
        sa.CheckConstraint(
            "reserved_quantity_grams >= 0",
            name=op.f("ck_produce_listings_reserved_qty_non_negative"),
        ),
        sa.CheckConstraint(
            "collected_quantity_grams >= 0",
            name=op.f("ck_produce_listings_collected_qty_non_negative"),
        ),
        sa.CheckConstraint(
            "available_quantity_grams + reserved_quantity_grams + collected_quantity_grams <= total_quantity_grams",
            name=op.f("ck_produce_listings_inventory_sum_within_total"),
        ),
        sa.CheckConstraint(
            "floor_price_paise_per_kg > 0", name=op.f("ck_produce_listings_floor_price_positive")
        ),
        sa.CheckConstraint(
            "spoilage_deadline_at > harvested_at",
            name=op.f("ck_produce_listings_deadline_after_harvest"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_produce_listings_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["crop_id"],
            ["crop_catalog.id"],
            name=op.f("fk_produce_listings_crop_id_crop_catalog"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["farmer_id"],
            ["users.id"],
            name=op.f("fk_produce_listings_farmer_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_produce_listings")),
    )
    op.create_index(
        "ix_produce_listings_farmer_status",
        "produce_listings",
        ["farmer_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_produce_listings_status_deadline",
        "produce_listings",
        ["status", "spoilage_deadline_at"],
        unique=False,
    )

    op.create_table(
        "auctions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("SCHEDULED", "OPEN", "CLOSING", "CLOSED", "CANCELLED", name="auction_status"),
            nullable=False,
        ),
        sa.Column("min_bid_paise_per_kg", sa.BigInteger(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("min_bid_paise_per_kg > 0", name=op.f("ck_auctions_min_bid_positive")),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_auctions_ends_after_starts")),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["produce_listings.id"],
            name=op.f("fk_auctions_listing_id_produce_listings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auctions")),
        sa.UniqueConstraint("listing_id", name=op.f("uq_auctions_listing_id")),
    )
    op.create_index("ix_auctions_status_ends_at", "auctions", ["status", "ends_at"], unique=False)

    op.create_table(
        "bid_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("auction_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("bid_price_paise_per_kg", sa.BigInteger(), nullable=False),
        sa.Column("requested_quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("min_acceptable_grams", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revision_number > 0", name=op.f("ck_bid_revisions_revision_positive")
        ),
        sa.CheckConstraint(
            "bid_price_paise_per_kg > 0", name=op.f("ck_bid_revisions_bid_price_positive")
        ),
        sa.CheckConstraint(
            "requested_quantity_grams > 0", name=op.f("ck_bid_revisions_requested_qty_positive")
        ),
        sa.CheckConstraint(
            "min_acceptable_grams > 0", name=op.f("ck_bid_revisions_min_acceptable_qty_positive")
        ),
        sa.CheckConstraint(
            "min_acceptable_grams <= requested_quantity_grams",
            name=op.f("ck_bid_revisions_min_qty_lte_requested"),
        ),
        sa.ForeignKeyConstraint(
            ["auction_id"],
            ["auctions.id"],
            name=op.f("fk_bid_revisions_auction_id_auctions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"],
            ["users.id"],
            name=op.f("fk_bid_revisions_buyer_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bid_revisions")),
        sa.UniqueConstraint("auction_id", "buyer_id", "revision_number", name="uq_bid_revision"),
    )
    op.create_index(
        "ix_bid_revisions_auction_active", "bid_revisions", ["auction_id", "is_active"], unique=False
    )

    op.create_table(
        "allocation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("auction_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "SOLVED", "INFEASIBLE", "FAILED", name="allocation_run_status"),
            nullable=False,
        ),
        sa.Column("solver_status", sa.String(length=50), nullable=False),
        sa.Column("objective_value_paise", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["auction_id"],
            ["auctions.id"],
            name=op.f("fk_allocation_runs_auction_id_auctions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allocation_runs")),
    )
    op.create_index("ix_allocation_runs_auction_id", "allocation_runs", ["auction_id"], unique=False)

    op.create_table(
        "allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("allocation_run_id", sa.Uuid(), nullable=False),
        sa.Column("auction_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("allocated_quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("unit_price_paise_per_kg", sa.BigInteger(), nullable=False),
        sa.Column("transport_cost_paise", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "allocated_quantity_grams > 0", name=op.f("ck_allocations_allocated_qty_positive")
        ),
        sa.CheckConstraint(
            "unit_price_paise_per_kg > 0", name=op.f("ck_allocations_unit_price_positive")
        ),
        sa.CheckConstraint(
            "transport_cost_paise >= 0", name=op.f("ck_allocations_transport_cost_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["allocation_run_id"],
            ["allocation_runs.id"],
            name=op.f("fk_allocations_allocation_run_id_allocation_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["auction_id"],
            ["auctions.id"],
            name=op.f("fk_allocations_auction_id_auctions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"],
            ["users.id"],
            name=op.f("fk_allocations_buyer_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allocations")),
    )
    op.create_index("ix_allocations_run_id", "allocations", ["allocation_run_id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("allocation_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("farmer_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING_CONFIRMATION",
                "CONFIRMED",
                "IN_TRANSIT",
                "COLLECTED",
                "CANCELLED_BY_BUYER",
                "RECOVERED",
                "EXPIRED",
                name="order_status",
            ),
            nullable=False,
        ),
        sa.Column("quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("total_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("transport_cost_paise", sa.BigInteger(), nullable=False),
        sa.Column("pickup_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_grams > 0", name=op.f("ck_orders_order_qty_positive")),
        sa.CheckConstraint(
            "total_amount_paise >= 0", name=op.f("ck_orders_order_amount_non_negative")
        ),
        sa.CheckConstraint(
            "transport_cost_paise >= 0", name=op.f("ck_orders_order_transport_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["allocation_id"],
            ["allocations.id"],
            name=op.f("fk_orders_allocation_id_allocations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"], ["users.id"], name=op.f("fk_orders_buyer_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["farmer_id"],
            ["users.id"],
            name=op.f("fk_orders_farmer_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["produce_listings.id"],
            name=op.f("fk_orders_listing_id_produce_listings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("allocation_id", name=op.f("uq_orders_allocation_id")),
    )
    op.create_index("ix_orders_buyer_status", "orders", ["buyer_id", "status"], unique=False)
    op.create_index("ix_orders_farmer_status", "orders", ["farmer_id", "status"], unique=False)

    op.create_table(
        "collection_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("collected_quantity_grams", sa.BigInteger(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "collected_quantity_grams > 0", name=op.f("ck_collection_records_collected_qty_positive")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_collection_records_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_records_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_records")),
        sa.UniqueConstraint("order_id", name=op.f("uq_collection_records_order_id")),
    )

    op.create_table(
        "transport_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("distance_meters", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_paise", sa.BigInteger(), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "distance_meters >= 0", name=op.f("ck_transport_quotes_distance_non_negative")
        ),
        sa.CheckConstraint(
            "estimated_cost_paise >= 0",
            name=op.f("ck_transport_quotes_estimated_cost_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"],
            ["users.id"],
            name=op.f("fk_transport_quotes_buyer_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["produce_listings.id"],
            name=op.f("fk_transport_quotes_listing_id_produce_listings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transport_quotes")),
    )
    op.create_index(
        "ix_transport_quotes_listing_buyer",
        "transport_quotes",
        ["listing_id", "buyer_id"],
        unique=False,
    )

    op.create_table(
        "buyer_reliability_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("score_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["buyer_id"],
            ["users.id"],
            name=op.f("fk_buyer_reliability_events_buyer_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_buyer_reliability_events_order_id_orders"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buyer_reliability_events")),
    )
    op.create_index(
        "ix_buyer_reliability_buyer_id", "buyer_reliability_events", ["buyer_id"], unique=False
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "ix_notifications_user_unread", "notifications", ["user_id", "is_read"], unique=False
    )

    op.create_table(
        "ivr_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("caller_phone", sa.String(length=20), nullable=False),
        sa.Column("session_state", sa.String(length=60), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ivr_sessions_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ivr_sessions")),
    )
    op.create_index("ix_ivr_sessions_caller_phone", "ivr_sessions", ["caller_phone"], unique=False)

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", JSON_TYPE, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_scheduled_jobs_job_attempts_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_jobs")),
    )
    op.create_index(
        "ix_scheduled_jobs_status_run_at", "scheduled_jobs", ["status", "run_at"], unique=False
    )

    op.create_table(
        "transactional_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", JSON_TYPE, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactional_outbox_events")),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "transactional_outbox_events",
        ["published_at", "created_at"],
        unique=False,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("acting_as_farmer_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", JSON_TYPE, nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["acting_as_farmer_id"],
            ["users.id"],
            name=op.f("fk_audit_events_acting_as_farmer_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_actor_created",
        "audit_events",
        ["actor_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"], unique=False
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.String(length=160), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body_json", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_idempotency_records_actor_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_records")),
        sa.UniqueConstraint(
            "idempotency_key",
            "actor_user_id",
            "endpoint",
            name="uq_idempotency_key_actor_endpoint",
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("audit_events")
    op.drop_table("transactional_outbox_events")
    op.drop_table("scheduled_jobs")
    op.drop_table("ivr_sessions")
    op.drop_table("notifications")
    op.drop_table("buyer_reliability_events")
    op.drop_table("transport_quotes")
    op.drop_table("collection_records")
    op.drop_table("orders")
    op.drop_table("allocations")
    op.drop_table("allocation_runs")
    op.drop_table("bid_revisions")
    op.drop_table("auctions")
    op.drop_table("produce_listings")
    op.drop_table("assisted_access_relationships")
    op.drop_table("buyer_profiles")
    op.drop_table("farmer_profiles")
    op.drop_table("refresh_tokens")
    op.drop_table("crop_catalog")
    op.drop_table("users")
    sa.Enum(name="order_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="allocation_run_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="auction_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="listing_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)

