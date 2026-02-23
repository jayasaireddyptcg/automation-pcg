from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.7
    tools: list[str] = []


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    tools: Optional[list[str]] = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str
    system_prompt: str
    model: str
    temperature: float
    tools: list
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
