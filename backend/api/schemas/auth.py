"""认证相关 Schema"""
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)
    nickname: str = Field(..., min_length=1, max_length=50)


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    nickname: str


class ProfileResponse(BaseModel):
    user_id: str
    phone: str
    nickname: str
    email: Optional[str] = None
    avatar: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    medical_info: Optional[dict] = None


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = None
    avatar: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    allergies: Optional[list[str]] = None
    chronic_diseases: Optional[list[str]] = None
    surgeries: Optional[list[str]] = None
    family_history: Optional[list[str]] = None
