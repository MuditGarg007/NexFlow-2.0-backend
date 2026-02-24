from pydantic import BaseModel


class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    correlation_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str
    llm: str
