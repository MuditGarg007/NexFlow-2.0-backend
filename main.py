from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import get_settings
from app.utils.logger import setup_logging, get_logger
from app.utils.correlation import CorrelationIdMiddleware
from app.middleware.cors import setup_cors
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.mcp.registry import init_registry

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_nexflow", environment=settings.ENVIRONMENT)
    init_registry()
    yield
    logger.info("shutting_down_nexflow")
    from app.redis import redis_client
    await redis_client.aclose()
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="NexFlow API",
    description="AI-Powered Workflow Manager — multi-agent orchestration with OAuth integrations",
    version="1.0.0",
    lifespan=lifespan,
)

setup_cors(app)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

from app.routers import auth, chat, integrations, health
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(integrations.router)
app.include_router(health.router)


@app.get("/")
async def root():
    return {
        "name": "NexFlow API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
