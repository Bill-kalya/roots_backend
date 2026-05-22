from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin

import enum


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True)

    provider = Column(String(50), nullable=False)  # mpesa | paypal
    provider_transaction_id = Column(String(255), nullable=True, unique=True)

    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), default="KES", nullable=False)

    # Optional raw payload for troubleshooting/audit (store small JSON string)
    raw_payload = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships are intentionally omitted to avoid circular imports in this repo layout.

