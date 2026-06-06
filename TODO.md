# TODO - Roots Backend Chat Persistence & Redis Pub/Sub

## Step 1: Add DB schema
- [x] Create `app/models/conversation.py` with `Conversation` model
- [x] Create `app/models/message.py` with `Message` model
- [x] Register models in `app/models/__init__.py` (or update existing imports)
- [x] Ensure Alembic `alembic/env.py` includes the new model metadata
- [x] Generate a new Alembic migration for `conversations` and `messages`


## Step 2: Redis pub/sub cross-worker fanout
- [ ] Create `app/pubsub.py` implementing Redis pub/sub manager
- [ ] Initialize pub/sub manager in `app/main.py` lifespan

## Step 3: Update websocket backend
- [ ] Replace in-memory room fanout in `app/api/routes/chat.py`
- [ ] Validate JWT token during websocket connect
- [ ] Authorize user membership to room
- [ ] Persist incoming messages to DB before publishing
- [ ] Load message history from DB on handshake/connect

## Step 4: Add room resolution endpoint
- [ ] Add `POST /api/conversations/resolve-room` endpoint
- [ ] Deterministic `room_id` derivation function

## Step 5: Migration + runtime testing
- [ ] Run `alembic upgrade head`
- [ ] Start uvicorn with `--workers 4` and verify cross-worker delivery
- [ ] Verify reconnect history loads correctly

