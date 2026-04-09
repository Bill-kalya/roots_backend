from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base, TimestampMixin

class Testimonial(Base, TimestampMixin):
    __tablename__ = "testimonials"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    location = Column(String(255))
    is_approved = Column(Boolean, default=False)