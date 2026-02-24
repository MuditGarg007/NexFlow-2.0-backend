"""Tests for app/dependencies.py (create_access_token, create_refresh_token)"""
import uuid
import pytest
from datetime import datetime, timezone
from jose import jwt

from app.dependencies import create_access_token, create_refresh_token
from app.config import get_settings

settings = get_settings()


def test_access_token_payload():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == user_id
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_refresh_token_payload():
    user_id = str(uuid.uuid4())
    token = create_refresh_token(user_id)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"
    assert "jti" in payload
    assert "exp" in payload


def test_refresh_token_has_unique_jti():
    user_id = str(uuid.uuid4())
    t1 = create_refresh_token(user_id)
    t2 = create_refresh_token(user_id)
    p1 = jwt.decode(t1, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    p2 = jwt.decode(t2, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert p1["jti"] != p2["jti"]


def test_access_token_wrong_secret_raises():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    with pytest.raises(Exception):
        jwt.decode(token, "wrong-secret", algorithms=[settings.ALGORITHM])
