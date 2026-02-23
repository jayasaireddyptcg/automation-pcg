from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.run import WorkflowRun, NodeRun
from app.models.workflow import Workflow
from app.models.user import User
from app.schemas.run import WorkflowRunResponse
from app.utils.auth import get_current_user_optional

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[WorkflowRunResponse])
async def list_runs(
    workflow_id: UUID | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    query = (
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.node_runs))
        .join(Workflow, WorkflowRun.workflow_id == Workflow.id)
        .where(Workflow.user_id == user.id)
    )
    if workflow_id:
        query = query.where(WorkflowRun.workflow_id == workflow_id)
    query = query.order_by(WorkflowRun.started_at.desc()).limit(limit)
    result = await db.execute(query)
    return [WorkflowRunResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.node_runs))
        .join(Workflow, WorkflowRun.workflow_id == Workflow.id)
        .where(WorkflowRun.id == run_id, Workflow.user_id == user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return WorkflowRunResponse.model_validate(run)
