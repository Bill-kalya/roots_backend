import enum
import uuid
from sqlalchemy import Column, ForeignKey, Enum, String, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship


from app.db.base import Base, TimestampMixin


class MessageStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    conversation_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # store plain text or ciphertext depending on encryption state
    content = Column(Text, nullable=False)

    encrypted = Column(Boolean, nullable=False, default=False, server_default="false")

    status = Column(
        Enum(
            MessageStatus,
            values_callable=lambda obj: [e.value for e in obj],
            name="messagestatus",
        ),
        default=MessageStatus.DELIVERED.value,
        nullable=False,
    )


    __table_args__ = (
        Index("ix_messages_conversation_created_at", "conversation_id", "created_at"),
    )

