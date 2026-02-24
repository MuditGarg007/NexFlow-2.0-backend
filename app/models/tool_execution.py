import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        Index("idx_tool_executions_session", "agent_session_id"),
        CheckConstraint("status IN ('pending', 'running', 'success', 'error')", name="ck_tool_exec_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False)
    integration_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("integrations.id"))
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    method_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_result: Mapped[dict | None] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_session = relationship("AgentSession", back_populates="tool_executions")
