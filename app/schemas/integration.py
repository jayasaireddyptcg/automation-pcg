from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class IntegrationCreate(BaseModel):
    name: str
    type: str
    credentials: dict[str, str]
    metadata: dict[str, Any] = {}


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    credentials: Optional[dict[str, str]] = None
    metadata: Optional[dict[str, Any]] = None


class IntegrationResponse(BaseModel):
    id: UUID
    name: str
    type: str
    metadata: Optional[dict[str, Any]] = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "IntegrationResponse":
        data = {
            "id": obj.id,
            "name": obj.name,
            "type": obj.type,
            "metadata": obj.metadata_ or {},
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)
