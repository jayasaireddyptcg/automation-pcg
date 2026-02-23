import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Float, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "running", "completed", "failed", "cancelled", name="run_status"),
        default="pending",
    )
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual")
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workflow = relationship("Workflow", back_populates="runs")
    node_runs = relationship("NodeRun", back_populates="run", cascade="all, delete-orphan", lazy="selectin")


class NodeRun(Base):
    __tablename__ = "node_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    node_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "running", "completed", "failed", "skipped", name="node_run_status"),
        default="pending",
    )
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run = relationship("WorkflowRun", back_populates="node_runs")
