from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
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


@router.get("/conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the current user."""
    stmt = (
        select(Conversation)
        .where(
            or_(
                Conversation.customer_id == current_user.id,
                Conversation.merchant_id == current_user.id,
            )
        )
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    items = []
    for conv in conversations:
        is_customer = conv.customer_id == current_user.id
        other_id = conv.merchant_id if is_customer else conv.customer_id

        other_user = await db.get(User, other_id)
        other_name = "Unknown"
        if other_user:
            other_name = (
                getattr(other_user, "store_name", None)
                or getattr(other_user, "full_name", None)
                or other_user.email
                or "Unknown"
            )

        last_msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg_result = await db.execute(last_msg_stmt)
        last_msg = last_msg_result.scalar_one_or_none()

        items.append({
            "room_id": conv.room_id,
            "other_user": {
                "id": str(other_id),
                "name": other_name,
            },
            "last_message": {
                "text": last_msg.content if last_msg else None,
                "time": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
                "sender_id": str(last_msg.sender_id) if last_msg else None,
            } if last_msg else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        })

    return {"conversations": items}


@router.post("/conversations/resolve-room")
async def resolve_room(
    body: ResolveRoomRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    merchant_id = body.merchant_id

    merchant_stmt = select(User).where(User.id == merchant_id, User.is_active == True)
    merchant = (await db.execute(merchant_stmt)).scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    room_id = make_room_id(current_user.id, merchant_id)

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


