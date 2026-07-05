from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship as orm_relationship
from sqlalchemy import String, Integer, Text, DateTime, Float, Boolean, ForeignKey, JSON, Enum as SAEnum
from datetime import datetime
from typing import Optional, List, AsyncGenerator
from backend.utils.config import settings
from backend.utils.logger import logger
import enum


def _pg_enum(enum_cls: type[enum.Enum], pg_name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=pg_name,
        native_enum=True,
        create_type=False,
        values_callable=lambda x: [e.value for e in x],
    )


class MeetingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class EntityType(str, enum.Enum):
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


class DecisionStatus(str, enum.Enum):
    ACTIVE = "active"
    REVISED = "revised"
    SUPERSEDED = "superseded"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    OVERDUE = "overdue"


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    ARCHIVED = "archived"


class DecisionAction(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    SUPERSEDED = "superseded"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ActivityType(str, enum.Enum):
    MEETING_ADDED = "meeting_added"
    DECISION_MADE = "decision_made"
    TASK_CREATED = "task_created"
    DECISION_UPDATED = "decision_updated"
    ENTITY_MERGED = "entity_merged"
    MEMORY_IMPROVED = "memory_improved"


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class TenantRole(str, enum.Enum):
    OWNER = "owner"
    MEMBER = "member"


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


# ─── Auth / Multi-tenant Models ───────────────────────────────────────────────

class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    memberships: Mapped[List["TenantMembershipModel"]] = orm_relationship(
        "TenantMembershipModel", back_populates="tenant", cascade="all, delete-orphan"
    )


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    memberships: Mapped[List["TenantMembershipModel"]] = orm_relationship(
        "TenantMembershipModel", back_populates="user", cascade="all, delete-orphan"
    )


class TenantMembershipModel(Base):
    __tablename__ = "tenant_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50), default="member", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["UserModel"] = orm_relationship("UserModel", back_populates="memberships")
    tenant: Mapped["TenantModel"] = orm_relationship("TenantModel", back_populates="memberships")


# ─── SQLAlchemy ORM Models ────────────────────────────────────────────────────

class MeetingModel(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[MeetingStatus] = mapped_column(_pg_enum(MeetingStatus, "meeting_status"), default=MeetingStatus.PENDING, nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(50), default="transcript")
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    entities: Mapped[List["MeetingEntityModel"]] = orm_relationship("MeetingEntityModel", back_populates="meeting", cascade="all, delete-orphan")
    decisions: Mapped[List["DecisionModel"]] = orm_relationship("DecisionModel", back_populates="meeting")
    tasks: Mapped[List["TaskModel"]] = orm_relationship("TaskModel", back_populates="meeting")


class EntityModel(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[EntityType] = mapped_column(_pg_enum(EntityType, "entity_type"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    canonical_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("entities.id"))

    meetings: Mapped[List["MeetingEntityModel"]] = orm_relationship("MeetingEntityModel", back_populates="entity")
    source_relationships: Mapped[List["EntityRelationshipModel"]] = orm_relationship(
        "EntityRelationshipModel",
        foreign_keys="EntityRelationshipModel.source_id",
        back_populates="source"
    )
    target_relationships: Mapped[List["EntityRelationshipModel"]] = orm_relationship(
        "EntityRelationshipModel",
        foreign_keys="EntityRelationshipModel.target_id",
        back_populates="target"
    )


class MeetingEntityModel(Base):
    __tablename__ = "meeting_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"))
    entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"))
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    context: Mapped[Optional[str]] = mapped_column(Text)

    meeting: Mapped["MeetingModel"] = orm_relationship("MeetingModel", back_populates="entities")
    entity: Mapped["EntityModel"] = orm_relationship("EntityModel", back_populates="meetings")


class EntityRelationshipModel(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"))
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"))
    relationship: Mapped[str] = mapped_column(String(200), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    meeting_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("meetings.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    source: Mapped["EntityModel"] = orm_relationship("EntityModel", foreign_keys="[EntityRelationshipModel.source_id]", back_populates="source_relationships")
    target: Mapped["EntityModel"] = orm_relationship("EntityModel", foreign_keys="[EntityRelationshipModel.target_id]", back_populates="target_relationships")


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(_pg_enum(ProjectStatus, "project_status"), default=ProjectStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DecisionModel(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[DecisionStatus] = mapped_column(_pg_enum(DecisionStatus, "decision_status"), default=DecisionStatus.ACTIVE)
    meeting_id: Mapped[int] = mapped_column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"))
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"))
    assigned_to: Mapped[Optional[str]] = mapped_column(String(200))
    pros: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    cons: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    reasons: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    meeting: Mapped["MeetingModel"] = orm_relationship("MeetingModel", back_populates="decisions")
    project: Mapped[Optional["ProjectModel"]] = orm_relationship("ProjectModel")
    history: Mapped[List["DecisionHistoryModel"]] = orm_relationship("DecisionHistoryModel", back_populates="decision", cascade="all, delete-orphan")


class DecisionHistoryModel(Base):
    __tablename__ = "decision_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(Integer, ForeignKey("decisions.id", ondelete="CASCADE"))
    meeting_id: Mapped[int] = mapped_column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"))
    action: Mapped[DecisionAction] = mapped_column(_pg_enum(DecisionAction, "decision_action"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    previous_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    decision: Mapped["DecisionModel"] = orm_relationship("DecisionModel", back_populates="history")
    meeting: Mapped["MeetingModel"] = orm_relationship("MeetingModel")


class TaskModel(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(_pg_enum(TaskStatus, "task_status"), default=TaskStatus.OPEN)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(200))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    meeting_id: Mapped[int] = mapped_column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"))
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    meeting: Mapped["MeetingModel"] = orm_relationship("MeetingModel", back_populates="tasks")
    project: Mapped[Optional["ProjectModel"]] = orm_relationship("ProjectModel")


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[ChatRole] = mapped_column(_pg_enum(ChatRole, "chat_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ActivityLogModel(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    type: Mapped[ActivityType] = mapped_column(_pg_enum(ActivityType, "activity_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    meeting_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("meetings.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables and apply lightweight schema migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_tenant_columns)
    logger.info("Database tables created successfully")


def _migrate_tenant_columns(conn) -> None:
    """Add tenant_id columns to existing tables when upgrading from single-tenant."""
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    migrations = [
        ("meetings", "tenant_id", "INTEGER REFERENCES tenants(id) ON DELETE CASCADE"),
        ("entities", "tenant_id", "INTEGER REFERENCES tenants(id) ON DELETE CASCADE"),
        ("chat_messages", "tenant_id", "INTEGER REFERENCES tenants(id) ON DELETE CASCADE"),
        ("activity_log", "tenant_id", "INTEGER REFERENCES tenants(id) ON DELETE CASCADE"),
    ]
    for table, column, col_type in migrations:
        if table not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table} ({column})"))
            logger.info("Added %s.%s column", table, column)
