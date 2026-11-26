import logging
import math
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.logistics.models import RoadDistanceCache

logger = logging.getLogger(__name__)

DistanceKind = Literal["ROAD_OSRM", "CACHED_ROAD_MATRIX", "APPROX_STRAIGHT_LINE"]


@dataclass(frozen=True)
class RouteEstimate:
    distance_meters: int
    estimated_travel_seconds: int
    distance_kind: DistanceKind
    provider_name: str
    is_approximate: bool
    disclaimer: str


class RoutingProvider(Protocol):
    def get_route(
        self,
        *,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> RouteEstimate: ...


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Calculate straight-line great-circle distance in meters."""
    r = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


class ApproximateHaversineProvider:
    """Fallback straight-line distance estimator when road routing is unavailable."""

    def get_route(
        self,
        *,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> RouteEstimate:
        dist_m = haversine_meters(origin_lat, origin_lon, dest_lat, dest_lon)
        # Approximate rural travel speed ~35 km/h (~9.72 m/s); not live traffic.
        est_seconds = max(60, round(dist_m / 9.72)) if dist_m > 0 else 0
        return RouteEstimate(
            distance_meters=dist_m,
            estimated_travel_seconds=est_seconds,
            distance_kind="APPROX_STRAIGHT_LINE",
            provider_name="local_haversine_fallback",
            is_approximate=True,
            disclaimer=(
                "Approximate straight-line distance and static travel estimate; "
                "not live road traffic."
            ),
        )


class OsrmRoutingProvider:
    """Optional OSRM HTTP routing provider with timeout and bounded retry."""

    def __init__(self, base_url: str, timeout_seconds: float = 2.5, max_retries: int = 1) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def get_route(
        self,
        *,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> RouteEstimate:
        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}?overview=false"
        )
        last_exc: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                route = data["routes"][0]
                return RouteEstimate(
                    distance_meters=round(float(route["distance"])),
                    estimated_travel_seconds=round(float(route["duration"])),
                    distance_kind="ROAD_OSRM",
                    provider_name="osrm",
                    is_approximate=False,
                    disclaimer="Estimated road distance/duration via OSRM; not live traffic.",
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"OSRM routing failed: {last_exc}")


def _coord_key(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def resolve_route_with_cache(
    db: Session,
    *,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    osrm_base_url: str | None = None,
    osrm_timeout_seconds: float = 2.5,
) -> RouteEstimate:
    """Check cached road matrix -> try optional OSRM -> fall back to straight-line Haversine."""
    o_key = _coord_key(origin_lat, origin_lon)
    d_key = _coord_key(dest_lat, dest_lon)

    cached = db.scalar(
        select(RoadDistanceCache).where(
            RoadDistanceCache.origin_key == o_key,
            RoadDistanceCache.dest_key == d_key,
        )
    )
    if cached is not None:
        return RouteEstimate(
            distance_meters=cached.distance_meters,
            estimated_travel_seconds=cached.duration_seconds,
            distance_kind="CACHED_ROAD_MATRIX",
            provider_name=cached.provider_name,
            is_approximate=False,
            disclaimer="Cached road distance/duration; not live traffic.",
        )

    if osrm_base_url:
        try:
            est = OsrmRoutingProvider(
                osrm_base_url, timeout_seconds=osrm_timeout_seconds
            ).get_route(
                origin_lat=origin_lat,
                origin_lon=origin_lon,
                dest_lat=dest_lat,
                dest_lon=dest_lon,
            )
            db.add(
                RoadDistanceCache(
                    origin_key=o_key,
                    dest_key=d_key,
                    distance_meters=est.distance_meters,
                    duration_seconds=est.estimated_travel_seconds,
                    provider_name=est.provider_name,
                )
            )
            db.flush()
            return est
        except Exception as exc:
            logger.warning("OSRM routing unavailable, falling back to Haversine: %s", exc)

    return ApproximateHaversineProvider().get_route(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
    )

