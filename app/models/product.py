from sqlalchemy import Column, String, Numeric, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from app.db.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    long_description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    image_url = Column(String(500), nullable=False)
    gallery = Column(ARRAY(Text), default=[])
    origin = Column(String(100), nullable=False)
    tag = Column(String(100))
    stock = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    artisan = Column(String(255), nullable=True)
    weight = Column(String(100), nullable=True)
    dimensions = Column(String(100), nullable=True)
    year = Column(Integer, nullable=True)
    materials = Column(ARRAY(Text), default=[])

