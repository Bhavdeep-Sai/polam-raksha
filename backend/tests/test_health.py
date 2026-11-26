from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.session import get_db
from app.main import app


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "PolamRaksha"
    assert "timestamp_utc" in data


def test_readiness_endpoint_succeeds_when_db_connected(client: TestClient) -> None:
    mock_db = MagicMock()
    mock_db.execute.return_value = 1

    def override_get_db() -> Generator[MagicMock, None, None]:
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    mock_db.execute.assert_called_once()


def test_readiness_endpoint_returns_503_when_db_unavailable(client: TestClient) -> None:
    mock_db = MagicMock()
    mock_db.execute.side_effect = OperationalError("SELECT 1", {}, Exception("db down"))

    def override_get_db() -> Generator[MagicMock, None, None]:
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "database_unavailable"


def test_openapi_schema_is_served(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/ready" in schema["paths"]


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret_key="change-me-in-local-env-min-32-chars")

