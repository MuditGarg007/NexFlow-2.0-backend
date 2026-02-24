"""Tests for app/config.py"""
import pytest
from app.config import Settings, get_settings


def test_default_settings():
    # Test that class defaults are correct by checking default field values directly
    import inspect
    fields = Settings.model_fields
    assert fields["ALGORITHM"].default == "HS256"
    assert fields["ACCESS_TOKEN_EXPIRE_MINUTES"].default == 15
    assert fields["REFRESH_TOKEN_EXPIRE_DAYS"].default == 7
    assert fields["RATE_LIMIT_CHAT"].default == 30
    assert fields["RATE_LIMIT_AUTH"].default == 5
    assert fields["MAX_TOOL_CALLS_PER_TURN"].default == 5
    assert fields["ENVIRONMENT"].default == "development"
    assert fields["LOG_LEVEL"].default == "INFO"
    assert fields["LLM_PROVIDER"].default == "openai"


def test_allowed_origins_list_single():
    s = Settings(
        SECRET_KEY="k",
        FERNET_KEY="ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=",
        ALLOWED_ORIGINS="http://localhost:3000",
    )
    assert s.allowed_origins_list == ["http://localhost:3000"]


def test_allowed_origins_list_multiple():
    s = Settings(
        SECRET_KEY="k",
        FERNET_KEY="ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=",
        ALLOWED_ORIGINS="http://localhost:3000, http://example.com",
    )
    assert s.allowed_origins_list == ["http://localhost:3000", "http://example.com"]


def test_get_settings_returns_settings_instance():
    s = get_settings()
    assert isinstance(s, Settings)
