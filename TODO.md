# TODO — Encrypted chat (deterministic room key)

## Plan steps
1. Backend config: add `CHAT_ENCRYPTION_SECRET: str = ""` to `app/core/config.py` Settings.
2. Backend endpoint: implement `GET /conversations/room-key` in `app/api/routes/conversations.py`:
   - validate `room_id` format `<customer_uuid>__<merchant_uuid>`
   - auth via `get_current_user`
   - authorize: current_user.id must equal one side
   - derive key: `HMAC-SHA256(CHAT_ENCRYPTION_SECRET, room_id)` → 64-char hex
   - if secret missing/empty → 500 (per requirements)
3. Frontend hook: update `../roots/src/hooks/useChat.js`:
   - add `encryptionStatus` state: `off | active | degraded`
   - implement `fetchAndInitKey(room_id)` that:
     - fetches `/conversations/room-key?room_id=...`
     - calls `initEncryption(keyHex)` from `../utils/encryption.js`
     - sets `encryptionStatus` accordingly
     - on failure sets `degraded` and continues
   - change init sequence to `resolveRoom() → fetchAndInitKey(room_id) → openSocket()`
   - ensure encryption is initialized before socket opens
4. Frontend UI: update `../roots/src/screens/Chat.jsx` to render encryption badge based on `encryptionStatus`.
5. Quick verification steps:
   - run backend and frontend locally
   - check `/conversations/room-key` returns 200 and a 64-char hex key
   - confirm first message after entering chat is encrypted when configured
   - confirm degraded mode when `CHAT_ENCRYPTION_SECRET` is empty

