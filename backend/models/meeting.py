from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MeetingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class ContentType(str, Enum):
    TRANSCRIPT = "transcript"
    NOTES = "notes"
    SUMMARY = "summary"


class MeetingInput(BaseModel):
    title: str = Field(..., min_length=1)
    date: datetime
    content: str = Field(..., min_length=1)
    content_type: ContentType = ContentType.TRANSCRIPT
    project_id: Optional[int] = None
    duration_minutes: Optional[int] = None
    tags: List[str] = []


class MeetingResponse(BaseModel):
    id: int
    title: str
    date: datetime
    status: MeetingStatus
    participant_count: int
    entity_count: int
    project_names: List[str] = []
    summary: Optional[str] = None
    duration_minutes: Optional[int] = None
    tags: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingDetailResponse(BaseModel):
    id: int
    title: str
    date: datetime
    status: MeetingStatus
    transcript: str
    summary: Optional[str] = None
    entities: List[dict] = []
    decisions: List[dict] = []
    tasks: List[dict] = []
    participants: List[dict] = []
    risks: List[str] = []
    blockers: List[str] = []
    topics: List[str] = []
    related_meetings: List[MeetingResponse] = []
    duration_minutes: Optional[int] = None

    class Config:
        from_attributes = True


class ProcessingStatusResponse(BaseModel):
    meeting_id: int
    status: str
    message: str
    progress: Optional[int] = None
