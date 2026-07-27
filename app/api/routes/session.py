import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter()


@router.get("/session-key")
async def get_session_key(
    current_user: User = Depends(get_current_user),
):
    """Derive a deterministic session encryption key for the current user."""
    secret: str = settings.CHAT_ENCRYPTION_SECRET
    if not secret:
        secret = "fallback-dev-secret-key"

    key_material = f"session:{current_user.id}"
    key_hex = hmac.new(
        secret.encode("utf-8"),
        key_material.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {"key": key_hex}
