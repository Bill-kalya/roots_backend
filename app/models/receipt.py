from sqlalchemy import Column, String, Text, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base, TimestampMixin


class Receipt(Base, TimestampMixin):
    __tablename__ = "receipts"

    # REC-xxxxxxxxxxxx
    id = Column(String(32), primary_key=True)

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Idempotency key (Stripe/PayPal/M-Pesa reference)
    payment_reference = Column(String(255), nullable=False, unique=True, index=True)

    # payment method snapshot: "card" | "paypal" | "mpesa"
    payment_method = Column(String(20), nullable=False)

    # HMAC-SHA256 hex digest
    signature = Column(String(64), nullable=False)

    # SHA-256(canonical_string) hex digest (auditable without secret)
    canonical_hash = Column(String(64), nullable=False, index=True)

    # Monetary snapshot
    subtotal = Column(Numeric(12, 2), nullable=False)
    shipping_fee = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="KES")

    # Customer snapshot
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False, index=True)

    # Full payload for re-rendering receipt HTML
    payload = Column(Text, nullable=False)

    # Status snapshot
    status = Column(String(20), nullable=False, default="paid")

    created_at = Column(DateTime, nullable=False)

