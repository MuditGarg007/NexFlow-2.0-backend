"""Tests for Pydantic schemas in app/schemas/"""
import pytest
from pydantic import ValidationError


# ── auth schemas ──────────────────────────────────────────────────────────────

class TestRegisterRequest:
    def test_valid(self):
        from app.schemas.auth import RegisterRequest
        r = RegisterRequest(email="user@example.com", password="strongpassword")
        assert r.email == "user@example.com"
        assert r.display_name is None

    def test_with_display_name(self):
        from app.schemas.auth import RegisterRequest
        r = RegisterRequest(email="user@example.com", password="strongpassword", display_name="Alice")
        assert r.display_name == "Alice"

    def test_invalid_email(self):
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(email="not-an-email", password="strongpassword")

    def test_password_too_short(self):
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="short")

    def test_password_too_long(self):
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="x" * 129)

    def test_display_name_too_long(self):
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="goodpassword", display_name="x" * 101)


class TestLoginRequest:
    def test_valid(self):
        from app.schemas.auth import LoginRequest
        r = LoginRequest(email="u@e.com", password="anypassword")
        assert r.email == "u@e.com"

    def test_invalid_email(self):
        from app.schemas.auth import LoginRequest
        with pytest.raises(ValidationError):
            LoginRequest(email="bad", password="pass")


class TestTokenResponse:
    def test_default_token_type(self):
        from app.schemas.auth import TokenResponse
        r = TokenResponse(access_token="a", refresh_token="r", expires_in=900)
        assert r.token_type == "bearer"


class TestUserResponse:
    def test_valid(self):
        from app.schemas.auth import UserResponse
        r = UserResponse(id="uid", email="u@e.com", display_name="Name", created_at="2024-01-01T00:00:00")
        assert r.id == "uid"

    def test_none_display_name(self):
        from app.schemas.auth import UserResponse
        r = UserResponse(id="uid", email="u@e.com", display_name=None, created_at="2024-01-01T00:00:00")
        assert r.display_name is None


# ── common schemas ────────────────────────────────────────────────────────────

class TestErrorResponse:
    def test_valid_without_optionals(self):
        from app.schemas.common import ErrorResponse
        r = ErrorResponse(type="https://example.com/error", title="Bad Request", status=400, detail="Something")
        assert r.instance is None
        assert r.correlation_id is None


class TestHealthResponse:
    def test_defaults(self):
        from app.schemas.common import HealthResponse
        r = HealthResponse(status="ok")
        assert r.version == "1.0.0"


class TestReadinessResponse:
    def test_fields(self):
        from app.schemas.common import ReadinessResponse
        r = ReadinessResponse(status="ok", database="ok", redis="ok", llm="not_configured")
        assert r.llm == "not_configured"
