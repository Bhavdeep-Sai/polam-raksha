import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, get_optional_current_user
from app.modules.listings.models import ListingStatus, ProduceListing
from app.modules.logistics.economics import (
    TransportResponsibility,
    calculate_transport_economics,
)
from app.modules.logistics.models import TransportQuote
from app.modules.logistics.routing import resolve_route_with_cache
from app.modules.orders.models import Order
from app.modules.users.models import AssistedAccessRelationship, BuyerProfile, User, UserRole

router = APIRouter(prefix="/logistics", tags=["logistics"])


class TransportQuoteRequest(BaseModel):
    listing_id: uuid.UUID
    dest_latitude: float | None = Field(default=None, ge=-90, le=90)
    dest_longitude: float | None = Field(default=None, ge=-180, le=180)
    quantity_grams: int = Field(gt=0)
    transport_responsibility: TransportResponsibility = "BUYER_PICKUP"
    fixed_pickup_cost_paise: int = Field(default=5000, ge=0)


class TransportQuoteResponse(BaseModel):
    quote_id: uuid.UUID
    listing_id: uuid.UUID
    distance_meters: int
    distance_kind: str
    is_approximate: bool
    estimated_travel_seconds: int
    fixed_pickup_cost_paise: int
    variable_cost_paise: int
    total_transport_cost_paise: int
    transport_responsibility: TransportResponsibility
    farmer_paid_cost_paise: int
    buyer_paid_cost_paise: int
    gross_sales_revenue_paise: int
    estimated_net_sales_revenue_paise: int
    provider_name: str
    disclaimer: str


class MapPointResponse(BaseModel):
    listing_id: uuid.UUID
    label: str
    latitude: float
    longitude: float
    is_exact: bool
    exact_pickup_address: str | None = None
    available_quantity_grams: int
    floor_price_paise_per_kg: int


@router.post(
    "/quote",
    response_model=TransportQuoteResponse,
    summary="Calculate route distance, travel estimate, and transport economics",
)
def create_transport_quote(
    payload: TransportQuoteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TransportQuoteResponse:
    listing = db.scalar(select(ProduceListing).where(ProduceListing.id == payload.listing_id))
    if listing is None:
        raise AppError(
            code="listing_not_found",
            message="Produce listing not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    origin_lat = listing.exact_latitude or listing.approx_latitude or 16.42
    origin_lon = listing.exact_longitude or listing.approx_longitude or 80.45

    dest_lat = payload.dest_latitude
    dest_lon = payload.dest_longitude
    if dest_lat is None or dest_lon is None:
        buyer_profile = db.scalar(
            select(BuyerProfile).where(BuyerProfile.user_id == current_user.id)
        )
        if (
            buyer_profile
            and buyer_profile.latitude is not None
            and buyer_profile.longitude is not None
        ):
            dest_lat = buyer_profile.latitude
            dest_lon = buyer_profile.longitude
        else:
            dest_lat = 16.5062
            dest_lon = 80.6480

    route = resolve_route_with_cache(
        db,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        osrm_base_url=settings.osrm_base_url,
        osrm_timeout_seconds=settings.osrm_timeout_seconds,
    )

    econ = calculate_transport_economics(
        quantity_grams=payload.quantity_grams,
        gross_unit_price_paise_per_kg=listing.floor_price_paise_per_kg,
        distance_meters=route.distance_meters,
        estimated_travel_seconds=route.estimated_travel_seconds,
        transport_responsibility=payload.transport_responsibility,
        fixed_pickup_cost_paise=payload.fixed_pickup_cost_paise,
    )

    quote = TransportQuote(
        listing_id=listing.id,
        buyer_id=current_user.id,
        distance_meters=route.distance_meters,
        distance_kind=route.distance_kind,
        estimated_travel_seconds=route.estimated_travel_seconds,
        fixed_pickup_cost_paise=econ.fixed_pickup_cost_paise,
        variable_cost_paise=econ.variable_cost_paise,
        estimated_cost_paise=econ.total_transport_cost_paise,
        transport_responsibility=econ.transport_responsibility,
        farmer_paid_cost_paise=econ.farmer_paid_cost_paise,
        provider_name=route.provider_name,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)

    return TransportQuoteResponse(
        quote_id=quote.id,
        listing_id=listing.id,
        distance_meters=route.distance_meters,
        distance_kind=route.distance_kind,
        is_approximate=route.is_approximate,
        estimated_travel_seconds=route.estimated_travel_seconds,
        fixed_pickup_cost_paise=econ.fixed_pickup_cost_paise,
        variable_cost_paise=econ.variable_cost_paise,
        total_transport_cost_paise=econ.total_transport_cost_paise,
        transport_responsibility=econ.transport_responsibility,
        farmer_paid_cost_paise=econ.farmer_paid_cost_paise,
        buyer_paid_cost_paise=econ.buyer_paid_cost_paise,
        gross_sales_revenue_paise=econ.gross_sales_revenue_paise,
        estimated_net_sales_revenue_paise=econ.estimated_net_sales_revenue_paise,
        provider_name=route.provider_name,
        disclaimer=route.disclaimer,
    )


@router.get(
    "/map-points",
    response_model=list[MapPointResponse],
    summary="List approximate produce map points (precise coords only for authorized participants)",
)
def get_map_points(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> list[MapPointResponse]:
    listings = db.scalars(
        select(ProduceListing).where(
            ProduceListing.status.in_(
                [
                    ListingStatus.ACTIVE,
                    ListingStatus.PARTIALLY_ALLOCATED,
                    ListingStatus.FULLY_ALLOCATED,
                ]
            )
        )
    ).all()

    authorized_farmer_ids: set[uuid.UUID] = set()
    authorized_listing_ids: set[uuid.UUID] = set()
    if current_user is not None and listings:
        if current_user.role == UserRole.OPERATOR:
            farmer_ids = {item.farmer_id for item in listings}
            authorized_farmer_ids = set(
                db.scalars(
                    select(AssistedAccessRelationship.farmer_id).where(
                        AssistedAccessRelationship.operator_id == current_user.id,
                        AssistedAccessRelationship.farmer_id.in_(farmer_ids),
                        AssistedAccessRelationship.is_active.is_(True),
                    )
                ).all()
            )
        elif current_user.role == UserRole.BUYER:
            listing_ids = [item.id for item in listings]
            authorized_listing_ids = set(
                db.scalars(
                    select(Order.listing_id).where(
                        Order.listing_id.in_(listing_ids),
                        Order.buyer_id == current_user.id,
                    )
                ).all()
            )

    points: list[MapPointResponse] = []
    for item in listings:
        lat = item.approx_latitude or 16.42
        lon = item.approx_longitude or 80.45
        is_exact = False
        exact_addr: str | None = None

        if current_user is not None:
            is_owner = current_user.id == item.farmer_id
            is_assigned_op = item.farmer_id in authorized_farmer_ids
            has_order = item.id in authorized_listing_ids
            if (is_owner or is_assigned_op or has_order) and item.exact_latitude is not None:
                lat = item.exact_latitude
                lon = item.exact_longitude or lon
                is_exact = True
                exact_addr = item.exact_pickup_address

        points.append(
            MapPointResponse(
                listing_id=item.id,
                label=item.approx_location_label,
                latitude=lat,
                longitude=lon,
                is_exact=is_exact,
                exact_pickup_address=exact_addr,
                available_quantity_grams=item.available_quantity_grams,
                floor_price_paise_per_kg=item.floor_price_paise_per_kg,
            )
        )
    return points
