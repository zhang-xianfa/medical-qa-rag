from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UpdateSessionRequest(BaseModel):
    status: Optional[str] = None
    max_rounds: Optional[int] = None


class MedicalRecordSummary(BaseModel):
    session_id: Optional[str] = None
    version: int = 0
    completion_level: str = "partial"
    chief_complaint: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    severity: Optional[int] = None
    accompanying_symptoms: list[str] = []
    collected_fields: list[str] = []
    missing_core_fields: list[str] = []


class SessionResponse(BaseModel):
    id: str
    user_id: str
    status: str
    intent: Optional[str] = None
    current_stage: Optional[str] = None
    red_flag_raised: bool = False
    round_count: int = 0
    max_rounds: int = 5
    close_reason: Optional[str] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    medical_record_summary: Optional[MedicalRecordSummary] = None
    message_count: int = 0
