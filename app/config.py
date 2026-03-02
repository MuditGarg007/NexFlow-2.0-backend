from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://nexflow:nexflow@localhost:5432/nexflow"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FERNET_KEY: str = "change-me"

    OPENAI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_DEFAULT_MODEL: str = "anthropic/claude-3.5-sonnet"
    LLM_PROVIDER: str = "openai"
    DEFAULT_MODEL: str = "gpt-5-mini"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""

    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "https://nexflow-2-0-backend.onrender.com"
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    RATE_LIMIT_CHAT: int = 30
    RATE_LIMIT_AUTH: int = 5
    RATE_LIMIT_TOOLS: int = 60
    MAX_TOOL_CALLS_PER_TURN: int = 5

    model_config = {"env_file": ".env", "case_sensitive": True}

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
