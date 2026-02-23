from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class NodeRunResponse(BaseModel):
    id: UUID
    node_id: str
    node_key: Optional[str] = None
    status: str
    input_data: dict
    output_data: dict
    error: Optional[str] = None
    execution_time_ms: float
    token_usage: Optional[dict] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowRunResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    status: str
    trigger_type: str
    input_payload: dict
    output_payload: dict
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    node_runs: list[NodeRunResponse] = []

    model_config = {"from_attributes": True}
