"""
Gmail integration routes for OAuth2 setup and testing.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.integration import Integration
from app.models.user import User
from app.schemas.integration import IntegrationCreate, IntegrationResponse
from app.utils.auth import get_current_user_optional
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.services.gmail_service import GmailService
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/gmail", tags=["gmail"])


class GmailCredentialsCreate(BaseModel):
    name: str
    access_token: str
    refresh_token: str
    client_id: str
    client_secret: str
    scopes: Optional[List[str]] = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailTestResponse(BaseModel):
    status: str
    message: str
    emails: Optional[List[Dict[str, Any]]] = None


@router.post("/setup", response_model=IntegrationResponse)
async def setup_gmail_integration(
    payload: GmailCredentialsCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    """
    Set up a new Gmail integration with OAuth2 credentials.
    
    Required credentials:
    - access_token: OAuth2 access token
    - refresh_token: OAuth2 refresh token
    - client_id: Google OAuth2 client ID
    - client_secret: Google OAuth2 client secret
    """
    credentials = {
        "access_token": payload.access_token,
        "refresh_token": payload.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": payload.client_id,
        "client_secret": payload.client_secret,
        "scopes": payload.scopes or ["https://www.googleapis.com/auth/gmail.readonly"]
    }
    
    try:
        gmail_service = GmailService(credentials)
        updated_creds = gmail_service.get_updated_credentials()
        
        integration = Integration(
            user_id=user.id,
            name=payload.name,
            type="gmail",
            credentials_encrypted=encrypt_credentials(updated_creds),
            status="active",
            metadata_={
                "email": "configured",
                "scopes": payload.scopes
            }
        )
        db.add(integration)
        await db.flush()
        
        return IntegrationResponse.model_validate(integration)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to setup Gmail integration: {str(e)}")


@router.post("/{integration_id}/test", response_model=GmailTestResponse)
async def test_gmail_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    """
    Test a Gmail integration by fetching recent unread emails.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.id,
            Integration.type == "gmail"
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Gmail integration not found")
    
    try:
        credentials = decrypt_credentials(integration.credentials_encrypted)
        gmail_service = GmailService(credentials)
        
        messages = gmail_service.get_unread_messages(max_results=5)
        
        updated_creds = gmail_service.get_updated_credentials()
        if updated_creds.get("access_token") != credentials.get("access_token"):
            integration.credentials_encrypted = encrypt_credentials(updated_creds)
            await db.flush()
        
        return GmailTestResponse(
            status="success",
            message=f"Successfully connected. Found {len(messages)} unread emails.",
            emails=messages
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to test Gmail integration: {str(e)}")


@router.post("/{integration_id}/poll-now")
async def poll_gmail_now(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    """
    Manually trigger polling for a specific Gmail integration.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.id,
            Integration.type == "gmail"
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Gmail integration not found")
    
    try:
        from app.services.gmail_poller import GmailPoller
        
        poller = GmailPoller(db)
        await poller._poll_integration(integration)
        
        return {"status": "success", "message": "Gmail polling triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to poll Gmail: {str(e)}")


@router.get("/oauth-instructions")
async def get_oauth_instructions():
    """
    Get instructions for setting up Gmail OAuth2 credentials.
    """
    return {
        "instructions": [
            "1. Go to Google Cloud Console: https://console.cloud.google.com/",
            "2. Create a new project or select an existing one",
            "3. Enable Gmail API: Navigate to 'APIs & Services' > 'Library' > Search 'Gmail API' > Enable",
            "4. Create OAuth2 Credentials:",
            "   - Go to 'APIs & Services' > 'Credentials'",
            "   - Click 'Create Credentials' > 'OAuth client ID'",
            "   - Application type: 'Web application'",
            "   - Add authorized redirect URIs (e.g., http://localhost:3000/auth/gmail/callback)",
            "5. Download the credentials JSON file",
            "6. Use the client_id and client_secret from the JSON file",
            "7. Generate access_token and refresh_token using OAuth2 flow:",
            "   - Use the OAuth2 playground: https://developers.google.com/oauthplayground/",
            "   - Or implement the OAuth2 flow in your frontend",
            "8. Required scopes: https://www.googleapis.com/auth/gmail.readonly",
            "9. Call /api/gmail/setup with the credentials"
        ],
        "required_scopes": [
            "https://www.googleapis.com/auth/gmail.readonly"
        ],
        "example_payload": {
            "name": "My Gmail Account",
            "access_token": "ya29.a0AfH6SMBx...",
            "refresh_token": "1//0gZ9X...",
            "client_id": "123456789.apps.googleusercontent.com",
            "client_secret": "GOCSPX-...",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
        }
    }
