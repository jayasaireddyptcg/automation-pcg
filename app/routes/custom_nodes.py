from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.custom_node import CustomNode
from app.models.user import User
from app.schemas.custom_node import CustomNodeCreate, CustomNodeUpdate, CustomNodeResponse
from app.utils.auth import get_current_user_optional

router = APIRouter(prefix="/custom-nodes", tags=["custom-nodes"])


@router.post("", response_model=CustomNodeResponse)
async def create_custom_node(
    payload: CustomNodeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    node = CustomNode(
        user_id=user.id,
        name=payload.name,
        icon=payload.icon,
        category=payload.category,
        color=payload.color,
        input_fields=[f.model_dump() for f in payload.input_fields],
        output_schema=payload.output_schema,
        api_endpoint=payload.api_endpoint,
        http_method=payload.http_method,
        headers=payload.headers,
        body_template=payload.body_template,
        auth_type=payload.auth_type,
        pre_transform_script=payload.pre_transform_script,
        post_transform_script=payload.post_transform_script,
    )
    db.add(node)
    await db.flush()
    return CustomNodeResponse.model_validate(node)


@router.get("", response_model=list[CustomNodeResponse])
async def list_custom_nodes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(CustomNode).where(CustomNode.user_id == user.id))
    return [CustomNodeResponse.model_validate(n) for n in result.scalars().all()]


@router.get("/{node_id}", response_model=CustomNodeResponse)
async def get_custom_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(CustomNode).where(CustomNode.id == node_id, CustomNode.user_id == user.id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Custom node not found")
    return CustomNodeResponse.model_validate(node)


@router.put("/{node_id}", response_model=CustomNodeResponse)
async def update_custom_node(
    node_id: UUID,
    payload: CustomNodeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(CustomNode).where(CustomNode.id == node_id, CustomNode.user_id == user.id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Custom node not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "input_fields" in update_data and update_data["input_fields"] is not None:
        update_data["input_fields"] = [f.model_dump() if hasattr(f, "model_dump") else f for f in update_data["input_fields"]]

    for key, value in update_data.items():
        setattr(node, key, value)

    await db.flush()
    return CustomNodeResponse.model_validate(node)


@router.delete("/{node_id}")
async def delete_custom_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(CustomNode).where(CustomNode.id == node_id, CustomNode.user_id == user.id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Custom node not found")
    await db.delete(node)
    return {"message": "Custom node deleted"}


@router.get("/{node_id}/export")
async def export_custom_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(CustomNode).where(CustomNode.id == node_id, CustomNode.user_id == user.id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Custom node not found")

    return {
        "name": node.name,
        "icon": node.icon,
        "category": node.category,
        "color": node.color,
        "input_fields": node.input_fields,
        "output_schema": node.output_schema,
        "api_endpoint": node.api_endpoint,
        "http_method": node.http_method,
        "headers": node.headers,
        "body_template": node.body_template,
        "auth_type": node.auth_type,
        "pre_transform_script": node.pre_transform_script,
        "post_transform_script": node.post_transform_script,
    }
