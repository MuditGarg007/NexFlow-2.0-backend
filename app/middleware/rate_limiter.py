from fastapi import Request, HTTPException, status
from app.redis import redis_client
from app.config import get_settings

settings = get_settings()


async def check_rate_limit(key: str, limit: int, window_seconds: int = 60):
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)
    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "type": "https://nexflow.app/errors/rate-limit",
                "title": "Rate Limit Exceeded",
                "status": 429,
                "detail": f"Too many requests. Limit is {limit} per {window_seconds}s.",
            },
        )


async def rate_limit_chat(request: Request):
    user_id = getattr(request.state, "user_id", "anon")
    await check_rate_limit(f"rate:chat:{user_id}", settings.RATE_LIMIT_CHAT)


async def rate_limit_auth(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"rate:auth:{client_ip}", settings.RATE_LIMIT_AUTH)
