# backend/models.py

from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, Field


class EmergencyLevel(IntEnum):
    RESUSCITATION = 1  # life-threatening, immediate resuscitation
    EMERGENCY = 2      # emergency department now
    URGENT = 3         # same-day medical review
    SEMI_URGENT = 4    # GP/clinic within 1-2 days
    NON_URGENT = 5     # home care and routine monitoring


class QueryRequest(BaseModel):
    symptoms: str = Field(..., min_length=1)
    child_age_months: int = Field(..., ge=0, le=216)  # 0-18 years
    language: str = Field(default="en", pattern="^(en|ar|fa)$")


class Citation(BaseModel):
    source: str
    chunk: str
    score: float
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: Optional[str] = None
    topic: Optional[str] = None
    content_type: Optional[str] = None
    source_type: Optional[str] = None
    source_priority: Optional[int] = None


class QueryResponse(BaseModel):
    answer: str

    # None = the request was never clinically triaged (true out-of-scope
    # refusals), as opposed to a triaged level of 1-5.
    emergency_level: Optional[EmergencyLevel] = None

    emergency_label: str
    citations: list[Citation] = Field(default_factory=list)
    see_doctor_urgency: str
    verified: bool = False
    refusal: bool = False

    # Lets evaluation and clients distinguish refusal causes
    # ("safety_critical" | "medication_misuse" | "scope").
    refusal_type: Optional[str] = None