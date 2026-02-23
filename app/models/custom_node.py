import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class CustomNode(Base):
    __tablename__ = "custom_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str] = mapped_column(String(100), default="puzzle")
    category: Mapped[str] = mapped_column(String(100), default="custom")
    color: Mapped[str] = mapped_column(String(20), default="#10b981")
    input_fields: Mapped[list] = mapped_column(JSONB, default=list)
    output_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    api_endpoint: Mapped[str] = mapped_column(Text, default="")
    http_method: Mapped[str] = mapped_column(String(10), default="POST")
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    body_template: Mapped[str] = mapped_column(Text, default="")
    auth_type: Mapped[str] = mapped_column(
        SAEnum("none", "bearer", "api_key", "basic", name="auth_type"),
        default="none",
    )
    pre_transform_script: Mapped[str] = mapped_column(Text, default="")
    post_transform_script: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
