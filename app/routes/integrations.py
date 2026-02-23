from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.integration import Integration
from app.models.user import User
from app.schemas.integration import IntegrationCreate, IntegrationUpdate, IntegrationResponse
from app.utils.auth import get_current_user_optional
from app.utils.encryption import encrypt_credentials, decrypt_credentials

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("", response_model=IntegrationResponse)
async def create_integration(
    payload: IntegrationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    integration = Integration(
        user_id=user.id,
        name=payload.name,
        type=payload.type,
        credentials_encrypted=encrypt_credentials(payload.credentials),
        metadata_=payload.metadata,
    )
    db.add(integration)
    await db.flush()
    return IntegrationResponse.model_validate(integration)


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(select(Integration).where(Integration.user_id == user.id))
    return [IntegrationResponse.model_validate(i) for i in result.scalars().all()]


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(
        select(Integration).where(Integration.id == integration_id, Integration.user_id == user.id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return IntegrationResponse.model_validate(integration)


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: UUID,
    payload: IntegrationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(
        select(Integration).where(Integration.id == integration_id, Integration.user_id == user.id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "credentials" in update_data:
        update_data["credentials_encrypted"] = encrypt_credentials(update_data.pop("credentials"))
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")

    for key, value in update_data.items():
        setattr(integration, key, value)

    await db.flush()
    return IntegrationResponse.model_validate(integration)


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    result = await db.execute(
        select(Integration).where(Integration.id == integration_id, Integration.user_id == user.id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    await db.delete(integration)
    return {"message": "Integration deleted"}
