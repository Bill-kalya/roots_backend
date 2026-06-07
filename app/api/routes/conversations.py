from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def make_room_id(customer_id: UUID, merchant_id: UUID) -> str:
    return f"{customer_id}__{merchant_id}"


class ResolveRoomRequest(BaseModel):
    merchant_id: UUID


def _parse_room_id(room_id: str) -> tuple[UUID | None, UUID | None]:
    """Split '<customer_uuid>__<merchant_uuid>' → (customer_id, merchant_id)."""
    if "__" not in room_id:
        return None, None
    left, right = room_id.split("__", 1)
    try:
        return UUID(left), UUID(right)
    except ValueError:
        return None, None


def _derive_room_key(room_id: str) -> str:
    """Deterministically derive a 256-bit AES key for a chat room.

    Algorithm: HMAC-SHA256(key=CHAT_ENCRYPTION_SECRET, msg=room_id)
    Output: 64-char lowercase hex string (32 bytes) suitable for AES-256.
    """
    import hashlib
    import hmac

    from app.core.config import settings

    secret: str = settings.CHAT_ENCRYPTION_SECRET
    if not secret:
        raise RuntimeError(
            "CHAT_ENCRYPTION_SECRET is not set. "
            "Add it to environment variables before enabling encrypted chat."
        )

    return hmac.new(
        secret.encode("utf-8"),
        room_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@router.post("/conversations/resolve-room")
async def resolve_room(
    body: ResolveRoomRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    merchant_id = body.merchant_id

    # Merchant must exist and be a merchant
    merchant_stmt = select(User).where(User.id == merchant_id, User.is_active == True)
    merchant = (await db.execute(merchant_stmt)).scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    # Compute deterministic room_id
    # Convention for UI: customer = current_user
    room_id = make_room_id(current_user.id, merchant_id)

    # Return without creating Conversation row (optional)
    return {
        "room_id": room_id,
        "customer_id": str(current_user.id),
        "merchant_id": str(merchant_id),
    }


@router.get("/conversations/room-key")
async def get_room_key(
    room_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return deterministic AES-256 key for a specific chat room."""

    customer_uuid, merchant_uuid = _parse_room_id(room_id)
    if not customer_uuid or not merchant_uuid:
        raise HTTPException(status_code=400, detail="Invalid room_id format")

    # Authorization: caller must be a participant
    if current_user.id != customer_uuid and current_user.id != merchant_uuid:
        raise HTTPException(
            status_code=403,
            detail="You are not a participant of this conversation",
        )

    try:
        key_hex = _derive_room_key(room_id)
    except RuntimeError:
        raise HTTPException(
            status_code=500,
            detail="Encryption service is not configured",
        )

    return {
        "key": key_hex,
        "room_id": room_id,
    }


