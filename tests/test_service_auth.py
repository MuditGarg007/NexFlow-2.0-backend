"""Tests for app/services/auth_service.py"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from passlib.context import CryptContext
from tests.conftest import make_execute_result

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture(autouse=True)
def mock_redis_globally(mock_redis):
    with patch("app.services.auth_service.redis_client", mock_redis):
        yield mock_redis


@pytest.mark.asyncio
async def test_register_new_user(mock_db):
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=None))
    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    user = await service.register("new@example.com", "password123", "NewUser")
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
    assert user.email == "new@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email_raises(mock_db, sample_user):
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=sample_user))
    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    with pytest.raises(ValueError, match="already registered"):
        await service.register("test@example.com", "password123")


@pytest.mark.asyncio
async def test_login_success(mock_db, mock_redis_globally):
    real_hashed = pwd_context.hash("correct_password")
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.hashed_password = real_hashed

    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=user))
    mock_redis_globally.setex = AsyncMock()

    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    result = await service.login("test@example.com", "correct_password")

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert isinstance(result["expires_in"], int)


@pytest.mark.asyncio
async def test_login_invalid_email_raises(mock_db):
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=None))
    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("noone@example.com", "pass")


@pytest.mark.asyncio
async def test_login_wrong_password_raises(mock_db):
    user = MagicMock()
    user.hashed_password = pwd_context.hash("real_password")
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=user))

    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("test@example.com", "wrong_password")


@pytest.mark.asyncio
async def test_refresh_tokens_valid(mock_db, mock_redis_globally):
    from app.dependencies import create_refresh_token
    user_id = str(uuid.uuid4())
    old_token = create_refresh_token(user_id)

    from jose import jwt as jose_jwt
    from app.config import get_settings
    settings = get_settings()
    payload = jose_jwt.decode(old_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    jti = payload["jti"]

    mock_redis_globally.get = AsyncMock(return_value=user_id)
    mock_redis_globally.delete = AsyncMock()
    mock_redis_globally.setex = AsyncMock()

    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    result = await service.refresh_tokens(old_token)

    assert "access_token" in result
    assert "refresh_token" in result
    mock_redis_globally.delete.assert_called_once_with(f"refresh:{jti}")


@pytest.mark.asyncio
async def test_refresh_tokens_invalid_token_raises(mock_db):
    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await service.refresh_tokens("garbage.token.value")


@pytest.mark.asyncio
async def test_refresh_tokens_revoked_raises(mock_db, mock_redis_globally):
    from app.dependencies import create_refresh_token
    user_id = str(uuid.uuid4())
    token = create_refresh_token(user_id)
    mock_redis_globally.get = AsyncMock(return_value=None)

    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    with pytest.raises(ValueError, match="revoked or expired"):
        await service.refresh_tokens(token)


@pytest.mark.asyncio
async def test_refresh_tokens_wrong_type_raises(mock_db):
    from app.dependencies import create_access_token
    from app.services.auth_service import AuthService
    access = create_access_token(str(uuid.uuid4()))
    service = AuthService(mock_db)
    with pytest.raises(ValueError, match="Invalid token type"):
        await service.refresh_tokens(access)


@pytest.mark.asyncio
async def test_logout_deletes_jti(mock_db, mock_redis_globally):
    from app.dependencies import create_refresh_token
    user_id = str(uuid.uuid4())
    token = create_refresh_token(user_id)
    from jose import jwt as jose_jwt
    from app.config import get_settings
    settings = get_settings()
    payload = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    jti = payload["jti"]

    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    await service.logout(token)
    mock_redis_globally.delete.assert_called_once_with(f"refresh:{jti}")


@pytest.mark.asyncio
async def test_logout_invalid_token_silently_ignored(mock_db, mock_redis_globally):
    from app.services.auth_service import AuthService
    service = AuthService(mock_db)
    await service.logout("completely.invalid.token")
    mock_redis_globally.delete.assert_not_called()
