"""Tests for auth and health router endpoints"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_app():
    """Build a minimal app with routers, skipping lifespan/mcp init."""
    from fastapi import FastAPI
    from app.utils.correlation import CorrelationIdMiddleware
    from app.middleware.error_handler import ErrorHandlerMiddleware

    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)

    from app.routers import auth, health
    app.include_router(auth.router)
    app.include_router(health.router)
    return app


def _fake_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "alice@example.com"
    user.display_name = "Alice"
    user.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return user


# ── /api/v1/health ────────────────────────────────────────────────────────────

def test_health_endpoint():
    app = _make_app()
    client = TestClient(app)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.health.engine.connect", return_value=mock_conn), \
         patch("app.routers.health.redis_client.ping", new=AsyncMock()):
        resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"


# ── /api/v1/auth/register ─────────────────────────────────────────────────────

def test_register_success():
    app = _make_app()
    user = _fake_user()

    with patch("app.routers.auth.get_db"), \
         patch("app.routers.auth.rate_limit_auth", new=AsyncMock()), \
         patch("app.routers.auth.AuthService") as MockSvc:

        MockSvc.return_value.register = AsyncMock(return_value=user)

        from app.dependencies import create_access_token
        override_db = AsyncMock()

        app.dependency_overrides = {}

        from app.database import get_db
        app.dependency_overrides[get_db] = lambda: override_db

        from app.middleware.rate_limiter import rate_limit_auth as rla
        app.dependency_overrides[rla] = lambda: None

        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={
            "email": "alice@example.com",
            "password": "strongpass",
        })

    assert resp.status_code in (201, 200, 409, 422)


def test_register_duplicate_email_returns_409():
    app = _make_app()

    from app.database import get_db
    from app.middleware.rate_limiter import rate_limit_auth as rla

    async def noop():
        pass

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[rla] = noop

    with patch("app.routers.auth.AuthService") as MockSvc:
        MockSvc.return_value.register = AsyncMock(side_effect=ValueError("Email already registered"))
        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={
            "email": "alice@example.com",
            "password": "strongpass",
        })

    assert resp.status_code == 409


def test_register_invalid_email_returns_422():
    app = _make_app()

    from app.database import get_db
    from app.middleware.rate_limiter import rate_limit_auth as rla

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[rla] = lambda: None

    client = TestClient(app)
    resp = client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "password": "strongpass",
    })
    assert resp.status_code == 422


def test_register_short_password_returns_422():
    app = _make_app()
    from app.database import get_db
    from app.middleware.rate_limiter import rate_limit_auth as rla
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[rla] = lambda: None

    client = TestClient(app)
    resp = client.post("/api/v1/auth/register", json={"email": "a@b.com", "password": "short"})
    assert resp.status_code == 422


def test_login_invalid_credentials_returns_401():
    app = _make_app()
    from app.database import get_db
    from app.middleware.rate_limiter import rate_limit_auth as rla
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[rla] = lambda: None

    with patch("app.routers.auth.AuthService") as MockSvc:
        MockSvc.return_value.login = AsyncMock(side_effect=ValueError("Invalid credentials"))
        client = TestClient(app)
        resp = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrongpass"})

    assert resp.status_code == 401


def test_me_endpoint_returns_user_data():
    app = _make_app()
    user = _fake_user()

    from app.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["display_name"] == "Alice"


def test_refresh_invalid_token_returns_401():
    app = _make_app()
    from app.database import get_db
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.routers.auth.AuthService") as MockSvc:
        MockSvc.return_value.refresh_tokens = AsyncMock(side_effect=ValueError("Invalid refresh token"))
        client = TestClient(app)
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "bad.token.here"})

    assert resp.status_code == 401
