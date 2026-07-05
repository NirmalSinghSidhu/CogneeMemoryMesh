from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EntityType(str, Enum):
    PERSON = "person"
    PROJECT = "project"
    TOPIC = "topic"
    DECISION = "decision"
    TASK = "task"
    RISK = "risk"
    BLOCKER = "blocker"
    DOCUMENT = "document"
    QUESTION = "question"
    DEADLINE = "deadline"


class DecisionStatus(str, Enum):
    ACTIVE = "active"
    REVISED = "revised"
    SUPERSEDED = "superseded"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    OVERDUE = "overdue"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    ARCHIVED = "archived"


class EntityResponse(BaseModel):
    id: int
    name: str
    type: EntityType
    description: Optional[str] = None
    meeting_count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    attributes: Dict[str, Any] = {}


class ParticipantResponse(BaseModel):
    id: int
    name: str
    role: Optional[str] = None
    email: Optional[str] = None
    meeting_count: int = 0


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    meeting_count: int = 0
    status: ProjectStatus = ProjectStatus.ACTIVE
    participant_count: int = 0
    decision_count: int = 0
    open_task_count: int = 0


class DecisionResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: DecisionStatus = DecisionStatus.ACTIVE
    meeting_id: int
    meeting_title: Optional[str] = None
    project_name: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime
    revision_count: int = 0


class DecisionHistoryEntry(BaseModel):
    meeting_id: int
    meeting_title: str
    date: datetime
    action: str
    description: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None


class DecisionEvolutionResponse(BaseModel):
    decision_id: int
    title: str
    current_status: str
    current_description: Optional[str] = None
    project_name: Optional[str] = None
    history: List[DecisionHistoryEntry] = []
    timeline: List[dict] = []
    pros: List[str] = []
    cons: List[str] = []
    reasons: List[str] = []


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.OPEN
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    project_name: Optional[str] = None
    meeting_id: int
    created_at: datetime
