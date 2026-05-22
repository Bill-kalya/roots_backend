from sqlalchemy import Column, String, Numeric, Integer, ForeignKey, Enum, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base, TimestampMixin
import enum


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)

    subtotal = Column(Numeric(10, 2), nullable=False)
    shipping_fee = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), nullable=False)

    # Payment fields (populated only by provider webhooks)
    payment_provider = Column(String(50), nullable=True)  # mpesa | paypal
    payment_reference = Column(String(255), nullable=True)  # provider transaction/capture id
    paid_at = Column(DateTime, nullable=True)

    # Cancellation fields referenced by OrderService
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(String(255), nullable=True)



class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    name_snapshot = Column(String(255), nullable=False)
    price_snapshot = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)