from dataclasses import dataclass
from typing import Literal

TransportResponsibility = Literal["BUYER_PICKUP", "FARMER_DELIVERY", "SHARED"]


@dataclass(frozen=True)
class TransportEconomicsResult:
    distance_meters: int
    estimated_travel_seconds: int
    fixed_pickup_cost_paise: int
    variable_cost_paise: int
    total_transport_cost_paise: int
    transport_responsibility: TransportResponsibility
    farmer_paid_cost_paise: int
    buyer_paid_cost_paise: int
    gross_sales_revenue_paise: int
    estimated_net_sales_revenue_paise: int


def calculate_transport_economics(
    *,
    quantity_grams: int,
    gross_unit_price_paise_per_kg: int,
    distance_meters: int,
    estimated_travel_seconds: int,
    transport_responsibility: TransportResponsibility = "BUYER_PICKUP",
    fixed_pickup_cost_paise: int = 5000,
    variable_rate_paise_per_km_per_ton: int = 1200,
) -> TransportEconomicsResult:
    """Compute integer-paise transport economics without double-charging."""
    if quantity_grams <= 0 or gross_unit_price_paise_per_kg <= 0:
        raise ValueError("quantity_grams and gross_unit_price_paise_per_kg must be positive")
    if distance_meters < 0 or fixed_pickup_cost_paise < 0 or variable_rate_paise_per_km_per_ton < 0:
        raise ValueError("distance and transport cost inputs must be non-negative")

    gross_sales = round((quantity_grams / 1000) * gross_unit_price_paise_per_kg)
    distance_km = distance_meters / 1000
    metric_tons = max(0.1, quantity_grams / 1_000_000)
    variable_cost = round(distance_km * metric_tons * variable_rate_paise_per_km_per_ton)
    total_transport = fixed_pickup_cost_paise + variable_cost

    if transport_responsibility == "BUYER_PICKUP":
        farmer_paid = 0
        buyer_paid = total_transport
    elif transport_responsibility == "FARMER_DELIVERY":
        farmer_paid = total_transport
        buyer_paid = 0
    else:
        farmer_paid = total_transport // 2
        buyer_paid = total_transport - farmer_paid

    return TransportEconomicsResult(
        distance_meters=distance_meters,
        estimated_travel_seconds=estimated_travel_seconds,
        fixed_pickup_cost_paise=fixed_pickup_cost_paise,
        variable_cost_paise=variable_cost,
        total_transport_cost_paise=total_transport,
        transport_responsibility=transport_responsibility,
        farmer_paid_cost_paise=farmer_paid,
        buyer_paid_cost_paise=buyer_paid,
        gross_sales_revenue_paise=gross_sales,
        estimated_net_sales_revenue_paise=gross_sales - farmer_paid,
    )

