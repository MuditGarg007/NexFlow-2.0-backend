"""Tests for app/middleware/rate_limiter.py and app/middleware/error_handler.py"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


# ── check_rate_limit ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_rate_limit_first_request_allowed(mock_redis):
    mock_redis.incr = AsyncMock(return_value=1)
    with patch("app.middleware.rate_limiter.redis_client", mock_redis):
        from app.middleware.rate_limiter import check_rate_limit
        await check_rate_limit("rate:test:user1", limit=5)
        mock_redis.expire.assert_called_once_with("rate:test:user1", 60)


@pytest.mark.asyncio
async def test_check_rate_limit_within_limit(mock_redis):
    mock_redis.incr = AsyncMock(return_value=3)
    with patch("app.middleware.rate_limiter.redis_client", mock_redis):
        from app.middleware.rate_limiter import check_rate_limit
        await check_rate_limit("rate:test:user1", limit=5)


@pytest.mark.asyncio
async def test_check_rate_limit_exactly_at_limit(mock_redis):
    mock_redis.incr = AsyncMock(return_value=5)
    with patch("app.middleware.rate_limiter.redis_client", mock_redis):
        from app.middleware.rate_limiter import check_rate_limit
        await check_rate_limit("rate:test:user1", limit=5)


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded_raises_429(mock_redis):
    mock_redis.incr = AsyncMock(return_value=6)
    with patch("app.middleware.rate_limiter.redis_client", mock_redis):
        from app.middleware.rate_limiter import check_rate_limit
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit("rate:test:user1", limit=5)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_check_rate_limit_custom_window(mock_redis):
    mock_redis.incr = AsyncMock(return_value=1)
    with patch("app.middleware.rate_limiter.redis_client", mock_redis):
        from app.middleware.rate_limiter import check_rate_limit
        await check_rate_limit("rate:test:user1", limit=10, window_seconds=300)
        mock_redis.expire.assert_called_once_with("rate:test:user1", 300)


@pytest.mark.asyncio
async def test_rate_limit_auth_uses_client_ip(mock_redis):
    mock_redis.incr = AsyncMock(return_value=1)
    request = MagicMock()
    request.client.host = "192.168.1.1"
    request.state = MagicMock()

    with patch("app.middleware.rate_limiter.redis_client", mock_redis), \
         patch("app.middleware.rate_limiter.settings") as s:
        s.RATE_LIMIT_AUTH = 5
        from app.middleware.rate_limiter import rate_limit_auth
        await rate_limit_auth(request)
        call_key = mock_redis.incr.call_args[0][0]
        assert "192.168.1.1" in call_key


@pytest.mark.asyncio
async def test_rate_limit_chat_uses_user_id(mock_redis):
    mock_redis.incr = AsyncMock(return_value=1)
    request = MagicMock()
    request.state.user_id = "user-uuid-123"

    with patch("app.middleware.rate_limiter.redis_client", mock_redis), \
         patch("app.middleware.rate_limiter.settings") as s:
        s.RATE_LIMIT_CHAT = 30
        from app.middleware.rate_limiter import rate_limit_chat
        await rate_limit_chat(request)
        call_key = mock_redis.incr.call_args[0][0]
        assert "user-uuid-123" in call_key


# ── ErrorHandlerMiddleware ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_error_handler_passes_through_on_success():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.middleware.error_handler import ErrorHandlerMiddleware

    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_error_handler_catches_unhandled_exception():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.middleware.error_handler import ErrorHandlerMiddleware

    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected boom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == 500
    assert "Internal Server Error" in body["title"]


# ── CorrelationIdMiddleware ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_correlation_id_is_generated_when_absent():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.utils.correlation import CorrelationIdMiddleware

    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    client = TestClient(app)
    resp = client.get("/ping")
    assert "X-Correlation-ID" in resp.headers
    cid = resp.headers["X-Correlation-ID"]
    import uuid
    uuid.UUID(cid)   # should not raise → valid UUID


@pytest.mark.asyncio
async def test_correlation_id_echoed_when_provided():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.utils.correlation import CorrelationIdMiddleware

    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    client = TestClient(app)
    resp = client.get("/ping", headers={"X-Correlation-ID": "my-custom-cid"})
    assert resp.headers["X-Correlation-ID"] == "my-custom-cid"
