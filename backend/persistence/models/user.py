"""用户模型"""
from sqlalchemy import Column, String, Integer, Float, Date, Boolean, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from persistence.database import Base
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    nickname = Column(String(50), nullable=False)

    # 个人中心字段（选填）
    email = Column(String(100))
    avatar = Column(String(500))
    birth_date = Column(Date)
    gender = Column(String(10))
    height = Column(Float)
    weight = Column(Float)
    blood_type = Column(String(5))
    medical_info = Column(JSON, default=dict)  # {"allergies":[], "chronic":[], "surgeries":[], "family":[]}

    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default="NOW()")
    updated_at = Column(TIMESTAMP(timezone=True), server_default="NOW()", onupdate="NOW()")
