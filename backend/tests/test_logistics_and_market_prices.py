from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.security import hash_secret
from app.db import models as _models  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.logistics.economics import calculate_transport_economics
from app.modules.logistics.routing import resolve_route_with_cache
from app.modules.market_prices.providers import (
    OptionalDataGovInProvider,
    normalize_price_to_paise_per_kg,
)
from app.modules.users.models import User, UserRole
from app.shared.time import utc_now


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_phase8.db"
    db_url = f"sqlite:///{db_file}"

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_transport_economics_buyer_pickup_does_not_reduce_farmer_revenue() -> None:
    buyer_pickup = calculate_transport_economics(
        quantity_grams=1_000_000,  # 1 metric ton
        gross_unit_price_paise_per_kg=2000,
        distance_meters=25_000,  # 25 km
        estimated_travel_seconds=2500,
        transport_responsibility="BUYER_PICKUP",
        fixed_pickup_cost_paise=5000,
        variable_rate_paise_per_km_per_ton=1200,
    )
    assert buyer_pickup.gross_sales_revenue_paise == 2_000_000
    assert buyer_pickup.variable_cost_paise == 30_000
    assert buyer_pickup.total_transport_cost_paise == 35_000
    assert buyer_pickup.farmer_paid_cost_paise == 0
    assert buyer_pickup.estimated_net_sales_revenue_paise == 2_000_000

    farmer_delivery = calculate_transport_economics(
        quantity_grams=1_000_000,
        gross_unit_price_paise_per_kg=2000,
        distance_meters=25_000,
        estimated_travel_seconds=2500,
        transport_responsibility="FARMER_DELIVERY",
        fixed_pickup_cost_paise=5000,
        variable_rate_paise_per_km_per_ton=1200,
    )
    assert farmer_delivery.farmer_paid_cost_paise == 35_000
    assert farmer_delivery.estimated_net_sales_revenue_paise == 1_965_000


def test_routing_failure_falls_back_to_labelled_approximate_distance(db_session: Session) -> None:
    # Unreachable OSRM URL should fail gracefully and fall back to Haversine
    route = resolve_route_with_cache(
        db_session,
        origin_lat=16.4167,
        origin_lon=80.4500,
        dest_lat=16.5062,
        dest_lon=80.6480,
        osrm_base_url="http://127.0.0.1:59999",
        osrm_timeout_seconds=0.3,
    )
    assert route.is_approximate is True
    assert route.distance_kind == "APPROX_STRAIGHT_LINE"
    assert route.distance_meters > 0
    assert "not live road traffic" in route.disclaimer.lower()


def test_market_price_unit_conversion_and_stale_detection(
    api_client: TestClient, db_session: Session
) -> None:
    assert normalize_price_to_paise_per_kg(240_000, "QUINTAL") == 2400
    assert normalize_price_to_paise_per_kg(2500, "KG") == 2500
    assert OptionalDataGovInProvider(api_key=None).fetch_records() == []

    admin = User(
        email="mkt_admin@example.com",
        phone_number="+919300000001",
        full_name="Market Admin",
        role=UserRole.ADMIN,
        password_hash=hash_secret("Pass!123"),
    )
    db_session.add(admin)
    db_session.commit()

    token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "mkt_admin@example.com", "password": "Pass!123"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}

    now = utc_now()
    old_obs = (now - timedelta(hours=96)).isoformat()
    fresh_obs = (now - timedelta(hours=2)).isoformat()

    csv_data = (
        "commodity_code,commodity_name_en,commodity_name_te,market_name,district,"
        "original_unit,original_price_paise,observed_at\n"
        f"TOMATO,Tomato,టమాటా,Guntur Yard,Guntur,QUINTAL,220000,{old_obs}\n"
        f"ONION,Onion,ఉల్లిపాయ,Tenali Yard,Guntur,KG,3100,{fresh_obs}\n"
    )
    imp = api_client.post(
        "/api/v1/market-prices/import",
        json={"csv_text": csv_data, "is_simulated": True},
        headers=hdr,
    )
    assert imp.status_code == 201, imp.text

    listed = api_client.get("/api/v1/market-prices")
    assert listed.status_code == 200
    items = {item["commodity_code"]: item for item in listed.json()}
    assert items["TOMATO"]["normalized_price_paise_per_kg"] == 2200
    assert items["TOMATO"]["is_stale"] is True
    assert items["TOMATO"]["is_simulated"] is True
    assert items["ONION"]["normalized_price_paise_per_kg"] == 3100
    assert items["ONION"]["is_stale"] is False


def test_unauthorized_users_cannot_access_precise_pickup_locations(
    api_client: TestClient, db_session: Session
) -> None:
    now = utc_now()
    crop = CropCatalog(code="TOMATO", name_en="Tomato", name_te="టమాటా", default_shelf_life_hours=48)
    farmer = User(
        email="loc_f@example.com",
        phone_number="+919300000002",
        full_name="Loc Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Pass!123"),
    )
    buyer = User(
        email="loc_b@example.com",
        phone_number="+919300000003",
        full_name="Loc Buyer",
        role=UserRole.BUYER,
        password_hash=hash_secret("Pass!123"),
    )
    db_session.add_all([crop, farmer, buyer])
    db_session.flush()

    listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=50_000,
        available_quantity_grams=50_000,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=2000,
        harvested_at=now - timedelta(hours=1),
        spoilage_deadline_at=now + timedelta(hours=12),
        approx_location_label="Tadikonda Mandal, Guntur",
        approx_latitude=16.4200,
        approx_longitude=80.4500,
        exact_pickup_address="Secret Farm Gate 44",
        exact_latitude=16.4167,
        exact_longitude=80.4512,
    )
    db_session.add(listing)
    db_session.commit()

    # Unauthenticated -> approximate only
    anon_pts = api_client.get("/api/v1/logistics/map-points")
    assert anon_pts.status_code == 200
    pt = anon_pts.json()[0]
    assert pt["is_exact"] is False
    assert pt["exact_pickup_address"] is None
    assert pt["latitude"] == 16.4200

    # Unauthorized buyer (no order) -> approximate only
    b_token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "loc_b@example.com", "password": "Pass!123"},
    ).json()["access_token"]
    buyer_pts = api_client.get(
        "/api/v1/logistics/map-points",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert buyer_pts.json()[0]["is_exact"] is False
    assert buyer_pts.json()[0]["exact_pickup_address"] is None

    # Owner farmer -> exact pickup location allowed
    f_token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "loc_f@example.com", "password": "Pass!123"},
    ).json()["access_token"]
    farmer_pts = api_client.get(
        "/api/v1/logistics/map-points",
        headers={"Authorization": f"Bearer {f_token}"},
    )
    assert farmer_pts.json()[0]["is_exact"] is True
    assert farmer_pts.json()[0]["exact_pickup_address"] == "Secret Farm Gate 44"
