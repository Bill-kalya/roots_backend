from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

# Simple in-memory room -> connections map
# NOTE: This is suitable for dev/single-process deployments.
# For production, use Redis pub/sub or a proper websocket backend.
rooms: dict[str, list[WebSocket]] = {}

router = APIRouter()


@router.websocket("/ws/chat/{room_id}")
async def chat_ws(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(None),
):
    """Basic chat websocket.

    Frontend (Chat.jsx) sends a JSON handshake frame:
      { "type": "handshake", "room_id": roomId }

    The backend must respond with:
      - { "type": "conversation", ... }
      - { "type": "history", messages: [...] }

    Until real persistence exists, we return safe placeholders.
    """

    await websocket.accept()

    rooms.setdefault(room_id, []).append(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            frame_type = data.get("type")

            # Handshake: acknowledge with expected frames so the UI doesn't crash.
            if frame_type == "handshake":
                # Send safe placeholder merchant so ChatHeader doesn't get stuck.
                await websocket.send_json(
                    {
                        "type": "conversation",
                        "conversation": {
                            "room_id": room_id,
                            "merchant": {
                                "name": "Roots Atelier",
                                "initials": "RA",
                                "online": True,
                                "responseTime": "Usually replies within 1 hour",
                            },
                            "pinned_product": None,
                        },
                    }
                )
                await websocket.send_json(
                    {
                        "type": "history",
                        "messages": [],
                    }
                )
                continue

            if frame_type == "message":
                # Broadcast to others in room
                for conn in list(rooms.get(room_id, [])):
                    if conn is websocket:
                        continue
                    try:
                        await conn.send_json(data)
                    except Exception:
                        try:
                            rooms[room_id].remove(conn)
                        except ValueError:
                            pass

                # Echo delivery receipt back to sender
                await websocket.send_json(
                    {
                        "type": "message",
                        "id": data.get("id"),
                        "from": data.get("from", "customer"),
                        "text": data.get("text", ""),
                        "time": data.get("time", ""),
                        "status": "delivered",
                    }
                )
                continue

            # Forward other frames (typing/read/etc) to everyone else in the room.
            for conn in list(rooms.get(room_id, [])):
                if conn is websocket:
                    continue
                try:
                    await conn.send_json(data)
                except Exception:
                    try:
                        rooms[room_id].remove(conn)
                    except ValueError:
                        pass

    except WebSocketDisconnect:
        conns = rooms.get(room_id, [])
        try:
            conns.remove(websocket)
        except ValueError:
            pass

        # Clean up empty rooms
        if not conns:
            rooms.pop(room_id, None)



