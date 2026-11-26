import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UtcDateTime
from app.shared.time import utc_now


class MarketReferencePrice(Base):
    __tablename__ = "market_reference_prices"
    __table_args__ = (
        CheckConstraint("original_price_paise > 0", name="market_orig_price_positive"),
        CheckConstraint(
            "normalized_price_paise_per_kg > 0", name="market_norm_price_positive"
        ),
        Index("ix_market_prices_commodity_obs", "commodity_code", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    commodity_code: Mapped[str] = mapped_column(String(50), nullable=False)
    commodity_name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    commodity_name_te: Mapped[str] = mapped_column(String(120), nullable=False)
    market_name: Mapped[str] = mapped_column(String(150), nullable=False)
    district: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False, default="Andhra Pradesh")
    grade: Mapped[str] = mapped_column(String(40), nullable=False, default="FAQ")
    price_type: Mapped[str] = mapped_column(String(20), nullable=False, default="MODAL")
    original_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="QUINTAL")
    original_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    normalized_price_paise_per_kg: Mapped[int] = mapped_column(BigInteger, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    source_name: Mapped[str] = mapped_column(String(60), nullable=False, default="CSV_IMPORT")
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)

