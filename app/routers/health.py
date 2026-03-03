from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
from app.redis import redis_client
from app.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.api_route("/health", methods=["GET", "HEAD"])
async def health():
    db_status = "ok"
    redis_status = "ok"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        await redis_client.ping()
    except Exception:
        redis_status = "error"

    all_healthy = all(s == "ok" for s in [db_status, redis_status])
    overall = "ok" if all_healthy else "degraded"
    status_code = 200 if all_healthy else 503

    body = HealthResponse(status=overall, database=db_status, redis=redis_status)
    return JSONResponse(content=body.model_dump(), status_code=status_code)


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness():
    db_status = "ok"
    redis_status = "ok"
    llm_status = "ok"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        await redis_client.ping()
    except Exception:
        redis_status = "error"

    try:
        from app.services.llm_client import get_llm_client
        llm = get_llm_client()
        if not llm.client.api_key:
            llm_status = "not_configured"
    except Exception:
        llm_status = "error"

    overall = "ok" if all(s == "ok" for s in [db_status, redis_status]) else "degraded"
    return ReadinessResponse(status=overall, database=db_status, redis=redis_status, llm=llm_status)
