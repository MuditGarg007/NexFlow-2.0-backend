"""Tests for app/services/integration_service.py"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import make_execute_result


@pytest.fixture(autouse=True)
def mock_redis_globally(mock_redis):
    with patch("app.services.integration_service.redis_client", mock_redis):
        yield mock_redis


# ── list_all / list_connected / get_connected_ids ────────────────────────────

@pytest.mark.asyncio
async def test_list_all_returns_active_integrations(mock_db):
    fake_integration = MagicMock(is_active=True)
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[fake_integration]))

    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    result = await service.list_all()
    assert result == [fake_integration]


@pytest.mark.asyncio
async def test_list_connected_returns_user_connections(mock_db, sample_user_id):
    conn = MagicMock()
    conn.integration_id = "github"
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[conn]))

    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    result = await service.list_connected(sample_user_id)
    assert result == [conn]


@pytest.mark.asyncio
async def test_get_connected_integration_ids(mock_db, sample_user_id):
    conn1 = MagicMock(integration_id="github")
    conn2 = MagicMock(integration_id="google")
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[conn1, conn2]))

    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    ids = await service.get_connected_integration_ids(sample_user_id)
    assert set(ids) == {"github", "google"}


# ── build_authorize_url ───────────────────────────────────────────────────────

def test_build_authorize_url_github(mock_db, mock_redis_globally):
    with patch("app.services.integration_service.settings") as s:
        s.GITHUB_CLIENT_ID = "gh-id"
        s.FRONTEND_URL = "http://localhost:3000"

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            with patch("asyncio.get_event_loop", return_value=loop):
                from app.services.integration_service import IntegrationService
                service = IntegrationService(mock_db)
                url = service.build_authorize_url("github", str(uuid.uuid4()))
        finally:
            loop.close()

    assert "github.com/login/oauth/authorize" in url
    assert "client_id=gh-id" in url
    assert "response_type=code" in url


def test_build_authorize_url_unknown_raises(mock_db):
    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    with pytest.raises(ValueError, match="Unknown integration"):
        service.build_authorize_url("unknown_provider", "uid")


def test_build_authorize_url_google_has_extra_params(mock_db, mock_redis_globally):
    with patch("app.services.integration_service.settings") as s:
        s.GOOGLE_CLIENT_ID = "google-id"
        s.FRONTEND_URL = "http://localhost:3000"

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            with patch("asyncio.get_event_loop", return_value=loop):
                from app.services.integration_service import IntegrationService
                service = IntegrationService(mock_db)
                url = service.build_authorize_url("google", str(uuid.uuid4()))
        finally:
            loop.close()

    assert "access_type=offline" in url
    assert "prompt=consent" in url


# ── handle_oauth_callback ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_oauth_callback_invalid_state_raises(mock_db, mock_redis_globally):
    mock_redis_globally.get = AsyncMock(return_value=None)
    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
        await service.handle_oauth_callback("github", "code123", "badstate")


@pytest.mark.asyncio
async def test_handle_oauth_callback_integration_mismatch_raises(mock_db, mock_redis_globally):
    user_id = str(uuid.uuid4())
    mock_redis_globally.get = AsyncMock(return_value=f"{user_id}:google")
    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    with pytest.raises(ValueError, match="Integration mismatch"):
        await service.handle_oauth_callback("github", "code123", "validstate")


# ── get_access_token ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_access_token_success(mock_db, sample_user_id):
    from cryptography.fernet import Fernet
    fkey = Fernet.generate_key()
    fernet = Fernet(fkey)
    encrypted = fernet.encrypt(b"real-token").decode()

    conn = MagicMock()
    conn.access_token_encrypted = encrypted
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=conn))

    with patch("app.utils.crypto.settings") as crypto_settings:
        crypto_settings.FERNET_KEY = fkey.decode()
        import app.utils.crypto as c
        c._fernet = None
        from app.services.integration_service import IntegrationService
        service = IntegrationService(mock_db)
        token = await service.get_access_token(sample_user_id, "github")
        assert token == "real-token"
        c._fernet = None


@pytest.mark.asyncio
async def test_get_access_token_not_found_raises(mock_db, sample_user_id):
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=None))
    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    with pytest.raises(ValueError, match="No connection found"):
        await service.get_access_token(sample_user_id, "github")


# ── disconnect ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_disconnect_existing_connection(mock_db, sample_user_id):
    conn = MagicMock()
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=conn))

    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    await service.disconnect(sample_user_id, "github")
    mock_db.delete.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_disconnect_nonexistent_connection_is_noop(mock_db, sample_user_id):
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=None))

    from app.services.integration_service import IntegrationService
    service = IntegrationService(mock_db)
    await service.disconnect(sample_user_id, "github")
    mock_db.delete.assert_not_called()
