import os
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Override settings before any app import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://nexflow:nexflow@localhost:5432/nexflow")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("FERNET_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_execute_result(scalar=None, scalars_all=None):
    """Return a plain MagicMock that looks like an sqlalchemy cursor result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    result.scalars.return_value.all.return_value = scalars_all if scalars_all is not None else []
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Async DB session mock.

    execute() is awaited in application code, so it must be AsyncMock.
    Its return_value is a plain MagicMock (not async) so that
    `result.scalar_one_or_none()` and `result.scalars().all()`
    behave as synchronous lookups rather than returning coroutines.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock(return_value=make_execute_result())
    return db


@pytest.fixture
def mock_redis():
    """Redis client mock."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    r.setex = AsyncMock()
    r.delete = AsyncMock()
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock()
    r.ping = AsyncMock(return_value=True)
    return r


@pytest.fixture
def sample_user_id():
    return uuid.uuid4()


@pytest.fixture
def sample_user(sample_user_id):
    user = MagicMock()
    user.id = sample_user_id
    user.email = "test@example.com"
    user.hashed_password = "$2b$12$placeholder_hash"
    user.display_name = "Test User"
    user.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    user.preferences = {}
    return user
