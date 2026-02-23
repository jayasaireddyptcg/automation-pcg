from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.utils.auth import get_current_user_optional

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    agent = Agent(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        model=payload.model,
        temperature=payload.temperature,
        tools=payload.tools,
    )
    db.add(agent)
    await db.flush()
    return AgentResponse.model_validate(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Agent).where(Agent.user_id == user.id))
    return [AgentResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.user_id == user.id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.user_id == user.id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    await db.flush()
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.user_id == user.id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    return {"message": "Agent deleted"}
