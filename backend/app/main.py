from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.modules.admin.router import router as admin_router
from app.modules.allocation.router import router as allocation_router
from app.modules.analytics.router import router as analytics_router
from app.modules.auctions.router import router as auctions_router
from app.modules.auctions.router import ws_router as auctions_ws_router
from app.modules.auth.router import router as auth_router
from app.modules.demo.router import router as demo_router
from app.modules.farmers.router import router as farmers_router
from app.modules.ivr.router import router as ivr_router
from app.modules.listings.router import crops_router
from app.modules.listings.router import router as listings_router
from app.modules.logistics.router import router as logistics_router
from app.modules.market_prices.router import router as market_prices_router
from app.modules.notifications.router import router as notifications_router
from app.modules.notifications.router import ws_router as notifications_ws_router
from app.modules.system.router import router as system_router


def create_app() -> FastAPI:
    """Create and configure the PolamRaksha FastAPI application."""
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title="PolamRaksha API",
        description="PolamRaksha (పొలంరక్ష) agricultural surplus recovery platform API",
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    api_v1_router = APIRouter(prefix=settings.api_v1_prefix)
    api_v1_router.include_router(system_router)
    api_v1_router.include_router(auth_router)
    api_v1_router.include_router(farmers_router)
    api_v1_router.include_router(crops_router)
    api_v1_router.include_router(listings_router)
    api_v1_router.include_router(auctions_router)
    api_v1_router.include_router(allocation_router)
    api_v1_router.include_router(ivr_router)
    api_v1_router.include_router(logistics_router)
    api_v1_router.include_router(market_prices_router)
    api_v1_router.include_router(notifications_router)
    api_v1_router.include_router(admin_router)
    api_v1_router.include_router(demo_router)
    api_v1_router.include_router(analytics_router)
    application.include_router(api_v1_router)
    application.include_router(auctions_ws_router)
    application.include_router(notifications_ws_router)

    return application


app = create_app()

