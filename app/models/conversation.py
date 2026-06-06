from sqlalchemy import Column, String, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from app.db.base import Base, TimestampMixin


class ConversationType(str, enum.Enum):
    DIRECT = "direct"


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Participant references (customer <-> merchant)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Room identity: deterministic on server using (customer_id, merchant_id)
    room_id = Column(String(200), nullable=False, index=True)

    # For future extensibility (e.g. group chats)
    type = Column(Enum(ConversationType), default=ConversationType.DIRECT, nullable=False)

    __table_args__ = (
        UniqueConstraint("customer_id", "merchant_id", name="uq_conversation_customer_merchant"),
        UniqueConstraint("room_id", name="uq_conversation_room_id"),
    )

