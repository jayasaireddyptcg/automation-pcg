from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.workflow import Workflow
from app.engine.executor import WorkflowExecutor
from app.schemas.run import WorkflowRunResponse

router = APIRouter(prefix="/webhook", tags=["webhooks"])


@router.post("/{workflow_id}")
async def trigger_webhook(
    workflow_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.status == "published"))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found or not published")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    executor = WorkflowExecutor(db)
    run = await executor.execute(workflow, payload, trigger_type="webhook")
    return WorkflowRunResponse.model_validate(run)
