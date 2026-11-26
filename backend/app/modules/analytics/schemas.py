from datetime import date

from pydantic import BaseModel


class ImpactMetricsSummary(BaseModel):
    is_simulated: bool
    dataset_label: str
    produce_listed_grams: int
    produce_allocated_grams: int
    produce_confirmed_grams: int
    produce_collected_grams: int
    surplus_produce_collected_grams: int
    rescued_from_waste_grams: int
    unmatched_produce_grams: int
    cancelled_quantity_grams: int
    recovered_after_cancellation_grams: int
    gross_transaction_value_paise: int
    estimated_net_sales_revenue_paise: int
    reported_payment_received_paise: int
    average_buyer_matching_time_seconds: int | None = None
    buyer_completion_rate_percent: float | None = None
    has_data: bool
    methodology_note: str
    baseline_note: str


class DailyImpactPoint(BaseModel):
    date_ist: str
    listed_kg: float
    allocated_kg: float
    collected_kg: float
    cancelled_kg: float


class CropImpactPoint(BaseModel):
    crop_code: str
    crop_name_en: str
    crop_name_te: str
    listed_kg: float
    collected_kg: float


class ImpactAnalyticsResponse(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    crop_code: str | None = None
    location: str | None = None
    timezone: str = "Asia/Kolkata"
    production: ImpactMetricsSummary
    demo_simulated: ImpactMetricsSummary | None = None
    daily_series: list[DailyImpactPoint]
    crop_breakdown: list[CropImpactPoint]

