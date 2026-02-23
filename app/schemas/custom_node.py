from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class CustomNodeFieldSchema(BaseModel):
    name: str
    label: str
    type: str  # string, number, boolean, select, textarea, json, file, expression
    required: bool = False
    default_value: Optional[Any] = None
    options: Optional[list[dict[str, str]]] = None
    placeholder: Optional[str] = None


class CustomNodeCreate(BaseModel):
    name: str
    icon: str = "puzzle"
    category: str = "custom"
    color: str = "#10b981"
    input_fields: list[CustomNodeFieldSchema] = []
    output_schema: dict[str, Any] = {}
    api_endpoint: str = ""
    http_method: str = "POST"
    headers: dict[str, str] = {}
    body_template: str = ""
    auth_type: str = "none"
    pre_transform_script: str = ""
    post_transform_script: str = ""


class CustomNodeUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    input_fields: Optional[list[CustomNodeFieldSchema]] = None
    output_schema: Optional[dict[str, Any]] = None
    api_endpoint: Optional[str] = None
    http_method: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    body_template: Optional[str] = None
    auth_type: Optional[str] = None
    pre_transform_script: Optional[str] = None
    post_transform_script: Optional[str] = None


class CustomNodeResponse(BaseModel):
    id: UUID
    name: str
    icon: str
    category: str
    color: str
    input_fields: list
    output_schema: dict
    api_endpoint: str
    http_method: str
    headers: dict
    body_template: str
    auth_type: str
    pre_transform_script: str
    post_transform_script: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
