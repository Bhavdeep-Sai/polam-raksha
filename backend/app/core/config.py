from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "PolamRaksha"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_v1_prefix: str = "/api/v1"

    jwt_secret_key: str = Field(
        default="change-me-in-local-env-min-32-chars",
        min_length=16,
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, ge=5, le=1440)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    pin_max_failed_attempts: int = Field(default=5, ge=3, le=20)
    pin_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    ivr_webhook_secret: str = Field(
        default="dev-ivr-webhook-secret-change-in-prod",
        min_length=12,
    )
    osrm_base_url: str | None = None
    osrm_timeout_seconds: float = Field(default=2.5, gt=0.2, le=15.0)
    data_gov_in_api_key: str | None = None
    market_price_stale_hours: int = Field(default=48, ge=1, le=720)
    cookie_secure: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    database_url: str = "postgresql+psycopg://polamraksha:polamraksha_dev_pass@localhost:5432/polamraksha"
    worker_poll_interval_seconds: int = Field(default=10, ge=1, le=3600)
    demo_mode_enabled: bool = False
    demo_auction_duration_seconds: int = Field(default=120, ge=15, le=3600)

    @field_validator("api_v1_prefix")
    @classmethod
    def ensure_leading_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            return f"/{value}"
        return value.rstrip("/")

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_default_secret_in_production(cls, value: str, info: object) -> str:
        data = getattr(info, "data", {})
        if data.get("app_env") == "production" and value.startswith("change-me"):
            raise ValueError("JWT_SECRET_KEY must be overridden in production")
        return value

    @field_validator("demo_mode_enabled")
    @classmethod
    def reject_demo_mode_in_production(cls, value: bool, info: object) -> bool:
        data = getattr(info, "data", {})
        if data.get("app_env") == "production" and value:
            raise ValueError("DEMO_MODE_ENABLED cannot be true in production")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

