from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin


class ShippingZone(Base, TimestampMixin):
    __tablename__ = "shipping_zones"

    id = Column(String(36), primary_key=True)  # use SERIAL in migration; kept string for ORM leniency
    country_code = Column(String(2), nullable=False, index=True, unique=True)
    base_rate = Column(Numeric(10, 2), nullable=False)
    per_kg_rate = Column(Numeric(10, 2), nullable=False)

