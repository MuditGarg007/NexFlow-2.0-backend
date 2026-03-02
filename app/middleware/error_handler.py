from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error("unhandled_exception", error=str(exc), path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "type": "https://nexflow.app/errors/internal",
                    "title": "Internal Server Error",
                    "status": 500,
                    "detail": "An unexpected error occurred.",
                },
                headers={"Access-Control-Allow-Origin": "*"},
            )
