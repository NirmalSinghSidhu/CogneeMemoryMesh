from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ForgetScope(str, Enum):
    MEETING = "meeting"
    PROJECT = "project"
    ENTITY = "entity"
    WORKSPACE = "workspace"


class RelationshipType(str, Enum):
    UPDATES = "updates"
    SUPERSEDES = "supersedes"
    CONFIRMS = "confirms"
    CONTRADICTS = "contradicts"
    REFINES = "refines"


class RememberInput(BaseModel):
    meeting_id: int
    force_reindex: bool = False


class RecallInput(BaseModel):
    query: str = Field(..., min_length=1)
    context_limit: int = 10
    meeting_ids: List[int] = []


class ImproveInput(BaseModel):
    meeting_id: int
    target_entity_id: int
    relationship_type: RelationshipType = RelationshipType.UPDATES


class ForgetInput(BaseModel):
    scope: ForgetScope
    target_id: Optional[int] = None
    reason: Optional[str] = None


class MemorySource(BaseModel):
    meeting_id: int
    meeting_title: str
    date: datetime
    entity_type: str
    entity_name: str


class RecallItem(BaseModel):
    content: str
    relevance_score: float
    entity_type: str
    entity_name: str
    meeting_id: Optional[int] = None
    meeting_title: Optional[str] = None
    date: Optional[datetime] = None


class MemoryResult(BaseModel):
    success: bool
    entities_processed: int = 0
    relationships_created: int = 0
    merged_entities: int = 0
    message: str = ""


class RecallResult(BaseModel):
    query: str
    results: List[RecallItem] = []
    sources: List[MemorySource] = []
    total: int = 0


class MemoryStats(BaseModel):
    total_meetings: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    total_decisions: int = 0
    total_tasks: int = 0
    entity_breakdown: Dict[str, int] = {}
    memory_size_mb: float = 0.0
    last_updated: Optional[datetime] = None


class OperationResult(BaseModel):
    success: bool
    message: str
    affected_count: int = 0


class CogneeHealth(BaseModel):
    active: bool
    message: str
    dataset_count: Optional[int] = None
    required: bool = False


class GraphNodeSummary(BaseModel):
    id: str
    label: str
    type: str
    weight: float = 1.0
    entity_id: Optional[int] = None
    color: Optional[str] = None
    description: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str
    weight: float = 1.0
    meeting_id: Optional[int] = None


class GraphData(BaseModel):
    nodes: List[GraphNodeSummary] = []
    edges: List[GraphEdge] = []
    node_count: int = 0
    edge_count: int = 0
    source: str = "sql"  # "cognee" | "sql"


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    entity_id: Optional[int] = None
    description: Optional[str] = None
    connections: List[GraphEdge] = []
    meetings: List[dict] = []
    attributes: Dict[str, Any] = {}


class SearchInput(BaseModel):
    query: str = Field(..., min_length=1)
    mode: str = "hybrid"
    entity_types: List[str] = []
    limit: int = 10


class SearchHit(BaseModel):
    id: int
    title: str
    type: str
    score: float
    excerpt: str
    meeting_id: Optional[int] = None
    meeting_title: Optional[str] = None
    date: Optional[datetime] = None
    entity_type: Optional[str] = None


class SearchResult(BaseModel):
    query: str
    results: List[SearchHit] = []
    total: int = 0
    search_mode: str = "hybrid"


class TopicSuggestion(BaseModel):
    topic: str
    related_meetings: List[str] = []
    last_discussed: datetime
    conflict_warning: Optional[str] = None
    meeting_count: int = 0


class ChatInput(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    context_limit: int = 5


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: List[MemorySource] = []
    decisions_referenced: List[dict] = []
    people_referenced: List[dict] = []
    meetings_referenced: List[dict] = []
    confidence: float = 0.0


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    sources: List[MemorySource] = []
    conversation_id: str
    created_at: datetime


class DashboardData(BaseModel):
    recent_meetings: List[dict] = []
    pending_tasks: List[dict] = []
    recent_decisions: List[dict] = []
    active_projects: List[dict] = []
    memory_stats: MemoryStats = MemoryStats()
    unresolved_blockers: List[str] = []
    overdue_tasks: List[dict] = []


class TopicFrequency(BaseModel):
    topic: str
    count: int
    last_mentioned: datetime
    trend: str = "stable"


class ActivityItem(BaseModel):
    id: str
    type: str
    title: str
    description: Optional[str] = None
    timestamp: datetime
    entity_id: Optional[int] = None
    meeting_id: Optional[int] = None


class TimelineEvent(BaseModel):
    id: str
    type: str
    title: str
    description: Optional[str] = None
    date: datetime
    meeting_id: Optional[int] = None
    meeting_title: Optional[str] = None
    entity_id: Optional[int] = None
    status: Optional[str] = None
    project_name: Optional[str] = None
    is_milestone: bool = False
