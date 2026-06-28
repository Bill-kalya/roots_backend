from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.cache.redis_manager import redis_manager
from app.core.dependencies import get_current_user  # noqa: F401
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def _make_message_payload(msg: Message) -> dict:
    # Frontend currently expects fields: id, from, text, time, status
    # We map sender_id -> "customer" / "merchant" based on whether sender is the websocket user
    # at publish time; so we only include sender_id and let caller map if needed.
    return {
        "type": "message",
        "id": str(msg.id),
        "conversation_id": str(msg.conversation_id),
        "sender_id": str(msg.sender_id),
        "content": msg.content,
        "status": msg.status,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _serialize_history(messages: list[Message]) -> list[dict]:
    # Order newest->oldest in DB; frontend shows given list order.
    out: list[dict] = []
    for m in messages:
        # Determine from-field: frontend uses "customer" for user messages, everything else treated as merchant.
        # Since we don’t know role here without current_user, we send “from” as sender_id string mapping
        # by convention: Chat.jsx compares message.from === "customer".
        # We'll set from = "customer" if sender matches current websocket user is done in caller.
        out.append(
            {
                "id": str(m.id),
                "from": "customer",
                "content": m.content,
                "time": m.created_at.strftime("%H:%M") if getattr(m, "created_at", None) else "",
                "status": m.status,
            }
        )
    return out


def _parse_room_id(room_id: str) -> tuple[Optional[UUID], Optional[UUID]]:
    # Deterministic room_id format in this codebase: <customer_id>__<merchant_id>
    if "__" not in room_id:
        return None, None
    left, right = room_id.split("__", 1)
    try:
        return UUID(left), UUID(right)
    except ValueError:
        return None, None


@router.websocket("/ws/chat/{room_id}")
async def chat_ws(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(None),
):
    # Token is required for production correctness; frontend passes ?token=access_token
    if not token:
        await websocket.close(code=4001, reason="token required")
        return

    # Authenticate websocket user

    # Decode token directly (token is passed as ?token=access_token)

    # decode via app.core.security.decode_token
    from app.core.security import decode_token

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001, reason="invalid token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="invalid token")
        return

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        await websocket.close(code=4001, reason="invalid token")
        return

    # Load user and validate active
    async with get_db() as db:
        user_stmt = select(User).where(User.id == user_uuid, User.is_active == True)
        user = (await db.execute(user_stmt)).scalar_one_or_none()

    if not user:
        await websocket.close(code=4001, reason="unauthorized")
        return

    # Authorization: user must be either customer or merchant for this deterministic room_id
    customer_id, merchant_id = _parse_room_id(room_id)
    if not customer_id or not merchant_id:
        await websocket.close(code=4003, reason="unauthorized")
        return

    if user.id != customer_id and user.id != merchant_id:
        await websocket.close(code=4003, reason="unauthorized")
        return

    await websocket.accept()

    # Redis pub/sub: subscribe this worker to room channel
    redis = redis_manager._client
    if not redis:
        await websocket.close(code=1011, reason="redis not initialized")
        return

    channel = f"room:{room_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    # Resolve conversation/merchant for UI
    async with get_db() as db:
        conv_stmt = select(Conversation).where(Conversation.room_id == room_id)
        conv = (await db.execute(conv_stmt)).scalar_one_or_none()

        merchant_user_stmt = select(User).where(User.id == merchant_id)
        merchant_user = (await db.execute(merchant_user_stmt)).scalar_one_or_none()


        # Load last 50 messages
        history_msgs: list[Message] = []
        if conv:
            history_stmt = (
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at.desc())
                .limit(50)
            )
            history_msgs = (await db.execute(history_stmt)).scalars().all()
        history_msgs = list(reversed(history_msgs))


    merchant_payload = {
        "name": getattr(merchant_user, "store_name", None) or getattr(merchant_user, "full_name", None) or "Merchant",
        "initials": "RA",
        "online": True,
        "responseTime": "Usually replies within 1 hour",
    }

    await websocket.send_json(
        {
            "type": "conversation",
            "conversation": {
                "room_id": room_id,
                "merchant": merchant_payload,
                "pinned_product": None,
            },
        }
    )

    # Convert history to frontend shape with proper from mapping
    history_out: list[dict] = []
    for m in history_msgs:
        is_customer = str(m.sender_id) == str(customer_id)
        history_out.append(
            {
                "id": str(m.id),
                "from": "customer" if is_customer else "merchant",
                "text": m.content,
                "encrypted": bool(getattr(m, "encrypted", False)),
                "time": m.created_at.strftime("%H:%M") if getattr(m, "created_at", None) else "",
                "status": m.status,
            }

        )

    await websocket.send_json({"type": "history", "messages": history_out})

    async def _publisher_loop():
        try:
            async for raw in pubsub.listen():

                if raw.get("type") != "message":
                    continue
                data = raw.get("data")
                if not data:
                    continue
                frame = json.loads(data) if isinstance(data, str) else data

                # frame contains persisted message; adapt to frontend
                msg = frame.get("message") or frame
                message_id = msg.get("id")
                sender_id = msg.get("sender_id")
                content = msg.get("content")
                status = msg.get("status", "delivered")
                created_at = msg.get("created_at")

                # created_at is ISO; frontend needs HH:MM
                time_str = ""
                if created_at:
                    try:
                        from datetime import datetime

                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        time_str = dt.strftime("%H:%M")
                    except Exception:
                        time_str = ""

                out = {
                    "type": "message",
                    "id": message_id,
                    "from": "customer" if sender_id == str(customer_id) else "merchant",
                    "content": content,
                    "encrypted": bool(msg.get("encrypted", False)),
                    "time": time_str,
                    "status": status,
                }

                await websocket.send_json(out)
        except WebSocketDisconnect:
            return

    listener_task = asyncio.create_task(_publisher_loop())

    try:
        while True:
            data = await websocket.receive_json()
            frame_type = data.get("type")

            if frame_type == "handshake":
                # Frontend already got conversation/history; ignore.
                continue

            if frame_type == "message":
                content = str(data.get("text") or data.get("content") or "").strip()
                if not content:
                    continue

                is_encrypted = bool(data.get("encrypted", False))
                sender_id = user.id

                # If message is encrypted, keep ciphertext in `content` (same as stored `msg.content`).
                # If message is not encrypted, `content` contains plaintext.



                # Ensure conversation exists; create if missing
                async with get_db() as db:
                    conv = (
                        (await db.execute(select(Conversation).where(Conversation.room_id == room_id))).scalar_one_or_none()
                    )
                    if not conv:
                        conv = Conversation(
                            customer_id=customer_id,
                            merchant_id=merchant_id,
                            room_id=room_id,
                        )
                        db.add(conv)
                        await db.commit()
                        await db.refresh(conv)

                    msg = Message(
                        conversation_id=conv.id,
                        sender_id=sender_id,
                        content=content,
                        encrypted=is_encrypted,
                        status="delivered",
                    )

                    db.add(msg)
                    await db.commit()
                    await db.refresh(msg)

                # Publish after persistence
                publish_payload = {
                    "type": "message",
                    "message": {
                        "id": str(msg.id),
                        "conversation_id": str(msg.conversation_id),
                        "sender_id": str(msg.sender_id),
                        "content": msg.content,
                        "encrypted": is_encrypted,
                        "status": msg.status,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    },
                }
                await redis.publish(channel, json.dumps(publish_payload))


            else:
                # typing/read/etc: ignore for now
                continue

    except WebSocketDisconnect:
        return
    finally:
        listener_task.cancel()
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass




