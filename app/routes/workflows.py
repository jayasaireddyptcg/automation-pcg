from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.models.run import WorkflowRun, NodeRun
from app.models.user import User
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from app.schemas.run import WorkflowRunResponse
from app.utils.auth import get_current_user_optional
from app.engine.executor import WorkflowExecutor

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    workflow = Workflow(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        agent_id=UUID(payload.agent_id) if payload.agent_id else None,
        variables=payload.variables,
        metadata_=payload.metadata,
    )
    db.add(workflow)
    await db.flush()

    # Add nodes
    for node_data in payload.nodes:
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_key=node_data.id,
            type=node_data.type,
            position_x=node_data.position.get("x", 0),
            position_y=node_data.position.get("y", 0),
            data=node_data.data,
            custom_node_id=UUID(node_data.custom_node_id) if node_data.custom_node_id else None,
        )
        db.add(node)

    # Add edges
    for edge_data in payload.edges:
        edge = WorkflowEdge(
            workflow_id=workflow.id,
            source=edge_data.source,
            target=edge_data.target,
            source_handle=edge_data.source_handle,
            target_handle=edge_data.target_handle,
            condition=edge_data.condition,
        )
        db.add(edge)

    await db.flush()

    # Refresh to get relationships
    result = await db.execute(select(Workflow).where(Workflow.id == workflow.id))
    workflow = result.scalar_one()
    return WorkflowResponse.model_validate(workflow)


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Workflow).where(Workflow.user_id == user.id))
    return [WorkflowResponse.model_validate(w) for w in result.scalars().all()]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowResponse.model_validate(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle nodes update
    if "nodes" in update_data and update_data["nodes"] is not None:
        # Delete existing nodes
        for existing_node in workflow.nodes:
            await db.delete(existing_node)
        # Add new nodes
        for node_data in payload.nodes:
            node = WorkflowNode(
                workflow_id=workflow.id,
                node_key=node_data.id,
                type=node_data.type,
                position_x=node_data.position.get("x", 0),
                position_y=node_data.position.get("y", 0),
                data=node_data.data,
                custom_node_id=UUID(node_data.custom_node_id) if node_data.custom_node_id else None,
            )
            db.add(node)
        del update_data["nodes"]

    # Handle edges update
    if "edges" in update_data and update_data["edges"] is not None:
        for existing_edge in workflow.edges:
            await db.delete(existing_edge)
        for edge_data in payload.edges:
            edge = WorkflowEdge(
                workflow_id=workflow.id,
                source=edge_data.source,
                target=edge_data.target,
                source_handle=edge_data.source_handle,
                target_handle=edge_data.target_handle,
                condition=edge_data.condition,
            )
            db.add(edge)
        del update_data["edges"]

    # Handle metadata rename
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")

    for key, value in update_data.items():
        if value is not None:
            setattr(workflow, key, value)

    await db.flush()
    result = await db.execute(select(Workflow).where(Workflow.id == workflow.id))
    workflow = result.scalar_one()
    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.status = "published"
    await db.flush()
    result = await db.execute(select(Workflow).where(Workflow.id == workflow.id))
    workflow = result.scalar_one()
    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/unpublish", response_model=WorkflowResponse)
async def unpublish_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.status = "draft"
    await db.flush()
    result = await db.execute(select(Workflow).where(Workflow.id == workflow.id))
    workflow = result.scalar_one()
    return WorkflowResponse.model_validate(workflow)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(workflow)
    return {"message": "Workflow deleted"}


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: UUID,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    executor = WorkflowExecutor(db)
    run = await executor.execute(workflow, payload, trigger_type="manual")

    # Re-fetch with node_runs eagerly loaded (node_runs has lazy="selectin" but
    # the run object returned by executor may be detached from the session)
    result = await db.execute(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.node_runs))
        .where(WorkflowRun.id == run.id)
    )
    run_loaded = result.scalar_one()
    return WorkflowRunResponse.model_validate(run_loaded)
