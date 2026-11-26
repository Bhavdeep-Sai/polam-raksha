import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.market_prices.models import MarketReferencePrice
from app.modules.market_prices.providers import (
    PriceUnit,
    normalize_price_to_paise_per_kg,
    parse_market_csv,
)
from app.modules.users.models import User, UserRole
from app.shared.time import utc_now

router = APIRouter(prefix="/market-prices", tags=["market-prices"])

REFERENCE_DISCLAIMER = (
    "Reference prices are historical/external observations only and are not "
    "guaranteed selling prices."
)


class MarketPriceResponse(BaseModel):
    id: uuid.UUID
    commodity_code: str
    commodity_name_en: str
    commodity_name_te: str
    market_name: str
    district: str
    state: str
    grade: str
    price_type: str
    original_unit: str
    original_price_paise: int
    normalized_price_paise_per_kg: int
    observed_at: datetime
    source_name: str
    is_stale: bool
    is_simulated: bool
    disclaimer: str = REFERENCE_DISCLAIMER


class ImportMarketJsonItem(BaseModel):
    commodity_code: str = Field(min_length=1, max_length=50)
    commodity_name_en: str = Field(min_length=1, max_length=120)
    commodity_name_te: str = Field(min_length=1, max_length=120)
    market_name: str = Field(min_length=1, max_length=150)
    district: str = Field(min_length=1, max_length=120)
    state: str = "Andhra Pradesh"
    grade: str = "FAQ"
    price_type: str = "MODAL"
    original_unit: PriceUnit = "QUINTAL"
    original_price_paise: int = Field(gt=0)
    observed_at: datetime
    source_name: str = "JSON_IMPORT"
    is_simulated: bool = False


class ImportMarketCsvRequest(BaseModel):
    csv_text: str | None = None
    items: list[ImportMarketJsonItem] = Field(default_factory=list)
    is_simulated: bool = False


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


@router.get(
    "",
    response_model=list[MarketPriceResponse],
    summary="List normalized market reference prices with freshness status",
)
def list_market_prices(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[MarketPriceResponse]:
    now = utc_now()
    stale_cutoff = timedelta(hours=settings.market_price_stale_hours)
    rows = db.scalars(
        select(MarketReferencePrice).order_by(MarketReferencePrice.observed_at.desc()).limit(50)
    ).all()
    return [
        MarketPriceResponse(
            id=row.id,
            commodity_code=row.commodity_code,
            commodity_name_en=row.commodity_name_en,
            commodity_name_te=row.commodity_name_te,
            market_name=row.market_name,
            district=row.district,
            state=row.state,
            grade=row.grade,
            price_type=row.price_type,
            original_unit=row.original_unit,
            original_price_paise=row.original_price_paise,
            normalized_price_paise_per_kg=row.normalized_price_paise_per_kg,
            observed_at=_ensure_utc(row.observed_at),
            source_name=row.source_name,
            is_stale=(now - _ensure_utc(row.observed_at)) > stale_cutoff,
            is_simulated=row.is_simulated,
        )
        for row in rows
    ]


@router.post(
    "/import",
    response_model=list[MarketPriceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Import CSV or JSON agricultural market reference prices (admin/operator)",
)
def import_market_prices(
    payload: ImportMarketCsvRequest,
    _actor: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[MarketPriceResponse]:
    created: list[MarketReferencePrice] = []
    if payload.csv_text:
        parsed = parse_market_csv(payload.csv_text, is_simulated=payload.is_simulated)
        for rec in parsed:
            row = MarketReferencePrice(
                commodity_code=rec.commodity_code,
                commodity_name_en=rec.commodity_name_en,
                commodity_name_te=rec.commodity_name_te,
                market_name=rec.market_name,
                district=rec.district,
                state=rec.state,
                grade=rec.grade,
                price_type=rec.price_type,
                original_unit=rec.original_unit,
                original_price_paise=rec.original_price_paise,
                normalized_price_paise_per_kg=rec.normalized_price_paise_per_kg,
                observed_at=rec.observed_at,
                source_name=rec.source_name,
                is_simulated=rec.is_simulated,
            )
            db.add(row)
            created.append(row)

    for item in payload.items:
        norm = normalize_price_to_paise_per_kg(item.original_price_paise, item.original_unit)
        row = MarketReferencePrice(
            commodity_code=item.commodity_code.upper(),
            commodity_name_en=item.commodity_name_en,
            commodity_name_te=item.commodity_name_te,
            market_name=item.market_name,
            district=item.district,
            state=item.state,
            grade=item.grade,
            price_type=item.price_type,
            original_unit=item.original_unit,
            original_price_paise=item.original_price_paise,
            normalized_price_paise_per_kg=norm,
            observed_at=_ensure_utc(item.observed_at),
            source_name=item.source_name,
            is_simulated=item.is_simulated or payload.is_simulated,
        )
        db.add(row)
        created.append(row)

    db.commit()
    now = utc_now()
    stale_cutoff = timedelta(hours=settings.market_price_stale_hours)
    return [
        MarketPriceResponse(
            id=row.id,
            commodity_code=row.commodity_code,
            commodity_name_en=row.commodity_name_en,
            commodity_name_te=row.commodity_name_te,
            market_name=row.market_name,
            district=row.district,
            state=row.state,
            grade=row.grade,
            price_type=row.price_type,
            original_unit=row.original_unit,
            original_price_paise=row.original_price_paise,
            normalized_price_paise_per_kg=row.normalized_price_paise_per_kg,
            observed_at=_ensure_utc(row.observed_at),
            source_name=row.source_name,
            is_stale=(now - _ensure_utc(row.observed_at)) > stale_cutoff,
            is_simulated=row.is_simulated,
        )
        for row in created
    ]
