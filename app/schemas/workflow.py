from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class WorkflowNodeSchema(BaseModel):
    id: str
    type: str
    position: dict[str, float]
    data: dict[str, Any] = {}
    custom_node_id: Optional[str] = None


class WorkflowEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None
    condition: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    agent_id: Optional[str] = None
    nodes: list[WorkflowNodeSchema] = []
    edges: list[WorkflowEdgeSchema] = []
    variables: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_id: Optional[str] = None
    status: Optional[str] = None
    nodes: Optional[list[WorkflowNodeSchema]] = None
    edges: Optional[list[WorkflowEdgeSchema]] = None
    variables: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class WorkflowNodeResponse(BaseModel):
    id: UUID
    node_key: str = ""
    type: str
    position_x: float
    position_y: float
    data: dict
    custom_node_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class WorkflowEdgeResponse(BaseModel):
    id: UUID
    source: str
    target: str
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None
    condition: Optional[str] = None

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: UUID
    name: str
    description: str
    agent_id: Optional[UUID] = None
    status: str
    variables: dict
    metadata: dict = {}
    nodes: list[WorkflowNodeResponse] = []
    edges: list[WorkflowEdgeResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "WorkflowResponse":
        data = {
            "id": obj.id,
            "name": obj.name,
            "description": obj.description,
            "agent_id": obj.agent_id,
            "status": obj.status,
            "variables": obj.variables or {},
            "metadata": obj.metadata_ or {},
            "nodes": [WorkflowNodeResponse.model_validate(n) for n in (obj.nodes or [])],
            "edges": [WorkflowEdgeResponse.model_validate(e) for e in (obj.edges or [])],
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)
