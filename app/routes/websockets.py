from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.models.user import User
from app.utils.auth import get_current_user_optional

router = APIRouter()


@router.websocket("/ws/execution")
async def websocket_execution(websocket: WebSocket):
    """
    WebSocket endpoint for real-time workflow execution updates.
    Currently accepts connections but doesn't stream execution yet.
    """
    await websocket.accept()
    try:
        while True:
            # Keep connection alive, wait for messages
            data = await websocket.receive_text()
            # Echo back for now (can be enhanced with real execution streaming)
            await websocket.send_json({"type": "ping", "message": "connected"})
    except WebSocketDisconnect:
        pass
