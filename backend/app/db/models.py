"""Central SQLAlchemy model registry for Alembic metadata discovery."""

from app.modules.allocation.models import Allocation, AllocationRun
from app.modules.auctions.models import Auction, BidRevision
from app.modules.ivr.models import IvrSession
from app.modules.listings.models import CropCatalog, ProduceListing
from app.modules.logistics.models import RoadDistanceCache, TransportQuote
from app.modules.market_prices.models import MarketReferencePrice
from app.modules.notifications.models import Notification
from app.modules.orders.models import CollectionRecord, DisputeCase, Order
from app.modules.reliability.models import BuyerReliabilityEvent
from app.modules.system.models import (
    AuditEvent,
    IdempotencyRecord,
    ScheduledJob,
    TransactionalOutboxEvent,
)
from app.modules.users.models import (
    AssistedAccessRelationship,
    BuyerProfile,
    FarmerProfile,
    RefreshToken,
    User,
)

__all__ = [
    "Allocation",
    "AllocationRun",
    "AssistedAccessRelationship",
    "Auction",
    "AuditEvent",
    "BidRevision",
    "BuyerProfile",
    "BuyerReliabilityEvent",
    "CollectionRecord",
    "CropCatalog",
    "DisputeCase",
    "FarmerProfile",
    "IdempotencyRecord",
    "IvrSession",
    "MarketReferencePrice",
    "Notification",
    "Order",
    "ProduceListing",
    "RefreshToken",
    "RoadDistanceCache",
    "ScheduledJob",
    "TransactionalOutboxEvent",
    "TransportQuote",
    "User",
]

