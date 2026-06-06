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

