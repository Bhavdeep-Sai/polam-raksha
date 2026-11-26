import csv
import io
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

import httpx

logger = logging.getLogger(__name__)

PriceUnit = Literal["KG", "QUINTAL"]


def normalize_price_to_paise_per_kg(price_paise: int, unit: PriceUnit) -> int:
    """Convert price in paise per KG or per QUINTAL (100 kg) into integer paise/kg."""
    if price_paise <= 0:
        raise ValueError("price_paise must be positive")
    if unit == "QUINTAL":
        return max(1, round(price_paise / 100))
    return price_paise


@dataclass(frozen=True)
class ImportedMarketRecord:
    commodity_code: str
    commodity_name_en: str
    commodity_name_te: str
    market_name: str
    district: str
    state: str
    grade: str
    price_type: str
    original_unit: PriceUnit
    original_price_paise: int
    normalized_price_paise_per_kg: int
    observed_at: datetime
    source_name: str
    is_simulated: bool


class MarketDataProvider(Protocol):
    def fetch_records(self) -> list[ImportedMarketRecord]: ...


def parse_market_csv(
    csv_text: str, *, source_name: str = "CSV_IMPORT", is_simulated: bool = False
) -> list[ImportedMarketRecord]:
    """Parse CSV market dataset with explicit unit normalization."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    records: list[ImportedMarketRecord] = []
    for row in reader:
        unit_raw = str(row.get("original_unit", "QUINTAL")).upper()
        unit: PriceUnit = "QUINTAL" if unit_raw == "QUINTAL" else "KG"
        orig_paise = int(row["original_price_paise"])
        obs_dt = datetime.fromisoformat(row["observed_at"])
        if obs_dt.tzinfo is None:
            obs_dt = obs_dt.replace(tzinfo=UTC)
        records.append(
            ImportedMarketRecord(
                commodity_code=str(row["commodity_code"]).upper(),
                commodity_name_en=str(row["commodity_name_en"]),
                commodity_name_te=str(row.get("commodity_name_te") or row["commodity_name_en"]),
                market_name=str(row["market_name"]),
                district=str(row["district"]),
                state=str(row.get("state", "Andhra Pradesh")),
                grade=str(row.get("grade", "FAQ")),
                price_type=str(row.get("price_type", "MODAL")),
                original_unit=unit,
                original_price_paise=orig_paise,
                normalized_price_paise_per_kg=normalize_price_to_paise_per_kg(orig_paise, unit),
                observed_at=obs_dt.astimezone(UTC),
                source_name=source_name,
                is_simulated=is_simulated,
            )
        )
    return records


class OptionalDataGovInProvider:
    """Optional Data.gov.in AGMARKNET API adapter; degrades gracefully without API key."""

    def __init__(
        self, api_key: str | None, resource_id: str = "9ef84268-d588-465a-a308-a864a43d0070"
    ) -> None:
        self.api_key = api_key
        self.resource_id = resource_id

    def fetch_records(self) -> list[ImportedMarketRecord]:
        if not self.api_key:
            return []
        url = f"https://api.data.gov.in/resource/{self.resource_id}"
        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(
                    url,
                    params={"api-key": self.api_key, "format": "json", "limit": 20},
                )
                resp.raise_for_status()
                payload: dict[str, Any] = resp.json()
            records: list[ImportedMarketRecord] = []
            for item in payload.get("records", []):
                modal_inr_quintal = int(float(item.get("modal_price", 0)))
                if modal_inr_quintal <= 0:
                    continue
                orig_paise = modal_inr_quintal * 100
                records.append(
                    ImportedMarketRecord(
                        commodity_code=str(item.get("commodity", "UNKNOWN")).upper()[:50],
                        commodity_name_en=str(item.get("commodity", "Unknown")),
                        commodity_name_te=str(item.get("commodity", "Unknown")),
                        market_name=str(item.get("market", "Unknown")),
                        district=str(item.get("district", "Unknown")),
                        state=str(item.get("state", "Andhra Pradesh")),
                        grade=str(item.get("grade", "FAQ")),
                        price_type="MODAL",
                        original_unit="QUINTAL",
                        original_price_paise=orig_paise,
                        normalized_price_paise_per_kg=normalize_price_to_paise_per_kg(
                            orig_paise, "QUINTAL"
                        ),
                        observed_at=datetime.now(UTC),
                        source_name="DATA_GOV_IN",
                        is_simulated=False,
                    )
                )
            return records
        except Exception as exc:
            logger.warning("Optional Data.gov.in fetch failed: %s", exc)
            return []
