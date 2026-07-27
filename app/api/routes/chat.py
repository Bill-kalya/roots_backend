from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.cache.redis_manager import redis_manager
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_room_id(room_id: str) -> tuple[Optional[UUID], Optional[UUID]]:
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
    if not token:
        await websocket.close(code=4001, reason="token required")
        return

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

    async with get_db() as db:
        user_stmt = select(User).where(User.id == user_uuid, User.is_active == True)
        user = (await db.execute(user_stmt)).scalar_one_or_none()

    if not user:
        await websocket.close(code=4001, reason="unauthorized")
        return

    customer_id, merchant_id = _parse_room_id(room_id)
    if not customer_id or not merchant_id:
        await websocket.close(code=4003, reason="unauthorized")
        return

    if user.id != customer_id and user.id != merchant_id:
        await websocket.close(code=4003, reason="unauthorized")
        return

    await websocket.accept()

    redis = redis_manager._client
    if not redis:
        await websocket.close(code=1011, reason="redis not initialized")
        return

    channel = f"room:{room_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    async with get_db() as db:
        conv_stmt = select(Conversation).where(Conversation.room_id == room_id)
        conv = (await db.execute(conv_stmt)).scalar_one_or_none()

        merchant_user_stmt = select(User).where(User.id == merchant_id)
        merchant_user = (await db.execute(merchant_user_stmt)).scalar_one_or_none()

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

                msg = frame.get("message") or frame
                message_id = msg.get("id")
                sender_id = msg.get("sender_id")
                content = msg.get("content")
                status = msg.get("status", "delivered")
                created_at = msg.get("created_at")

                time_str = ""
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        time_str = dt.strftime("%H:%M")
                    except Exception:
                        time_str = ""

                out = {
                    "type": "message",
                    "id": message_id,
                    "from": "customer" if sender_id == str(customer_id) else "merchant",
                    "text": content,
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
                continue

            if frame_type == "message":
                content = str(data.get("content") or data.get("text") or "").strip()
                if not content:
                    continue

                is_encrypted = bool(data.get("encrypted", False))
                sender_id = user.id

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

            elif frame_type == "typing":
                await redis.publish(
                    channel,
                    json.dumps({
                        "type": "typing",
                        "user_id": str(user.id),
                        "typing": data.get("typing", False),
                    }),
                )

            elif frame_type == "read":
                message_id = data.get("message_id")
                if message_id:
                    async with get_db() as db:
                        msg_stmt = select(Message).where(Message.id == message_id)
                        msg = (await db.execute(msg_stmt)).scalar_one_or_none()
                        if msg and str(msg.sender_id) != str(user.id):
                            msg.status = "read"
                            await db.commit()

                    await redis.publish(
                        channel,
                        json.dumps({
                            "type": "read",
                            "message_id": message_id,
                            "reader_id": str(user.id),
                        }),
                    )

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
