from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.sql import func

from ..core.database import Base


class User(Base):
    __tablename__ = "users"
    user_id = Column(String(50), primary_key=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String)
    email = Column(String(254))
    password_hash = Column(String(255))
    fcm_token = Column(Text)
    role = Column(String(30), default="FARMER")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
