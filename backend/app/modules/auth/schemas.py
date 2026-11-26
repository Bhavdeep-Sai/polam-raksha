import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.users.models import UserRole


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    role: Literal[UserRole.FARMER, UserRole.BUYER]
    email: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, min_length=10, max_length=20)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    pin: str | None = Field(default=None, pattern=r"^\d{4,6}$")
    preferred_language: Literal["te", "en"] = "te"

    # Optional farmer profile fields
    village: str | None = Field(default=None, max_length=120)
    mandal: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    exact_pickup_address: str | None = Field(default=None, max_length=500)

    # Optional buyer profile fields
    business_name: str | None = Field(default=None, max_length=180)
    buyer_type: str | None = Field(default="wholesaler", max_length=60)

    @model_validator(mode="after")
    def validate_credentials(self) -> "RegisterRequest":
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number is required")
        if not self.password and not self.pin:
            raise ValueError("Either password or keypad PIN is required")
        if self.pin and not self.phone_number:
            raise ValueError("phone_number is required when setting a keypad PIN")
        return self


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class PinLoginRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)
    pin: str = Field(pattern=r"^\d{4,6}$")


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class UserSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    role: UserRole
    preferred_language: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in_seconds: int
    user: UserSummary


class LogoutResponse(BaseModel):
    status: Literal["logged_out"] = "logged_out"

