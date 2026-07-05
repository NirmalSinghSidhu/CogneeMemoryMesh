from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import List
from datetime import datetime, timedelta

from backend.database.connection import (
    get_db, MeetingModel, EntityModel, DecisionModel, TaskModel,
    ProjectModel, ActivityLogModel, MeetingEntityModel, EntityRelationshipModel,
)
from backend.models.memory import (
    DashboardData, MemoryStats, TopicFrequency, ActivityItem
)
from backend.api.dependencies.auth import CurrentUser, get_current_user
from backend.utils.logger import logger

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardData)
async def get_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get complete dashboard summary."""
    tenant_id = current_user.tenant_id
    # Recent meetings (last 5)
    m_result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.tenant_id == tenant_id)
        .order_by(MeetingModel.date.desc())
        .limit(5)
    )
    recent_meetings_raw = m_result.scalars().all()
    recent_meetings = []
    for m in recent_meetings_raw:
        e_count = (await db.execute(
            select(func.count(MeetingEntityModel.id)).where(MeetingEntityModel.meeting_id == m.id)
        )).scalar() or 0
        p_count = (await db.execute(
            select(func.count(MeetingEntityModel.id))
            .join(EntityModel, EntityModel.id == MeetingEntityModel.entity_id)
            .where(and_(MeetingEntityModel.meeting_id == m.id, EntityModel.type == "person"))
        )).scalar() or 0
        recent_meetings.append({
            "id": m.id, "title": m.title, "date": m.date.isoformat(),
            "status": m.status, "participant_count": p_count,
            "entity_count": e_count, "project_names": [], "summary": m.summary,
            "duration_minutes": m.duration_minutes, "tags": m.tags or [],
            "created_at": m.created_at.isoformat(),
        })

    # Pending tasks
    t_result = await db.execute(
        select(TaskModel)
        .join(MeetingModel, MeetingModel.id == TaskModel.meeting_id)
        .where(
            MeetingModel.tenant_id == tenant_id,
            TaskModel.status.in_(["open", "in_progress"]),
        )
        .order_by(TaskModel.created_at.desc()).limit(5)
    )
    pending_tasks = []
    for t in t_result.scalars().all():
        proj_name = None
        if t.project_id:
            p = (await db.execute(select(ProjectModel).where(ProjectModel.id == t.project_id))).scalar_one_or_none()
            proj_name = p.name if p else None
        pending_tasks.append({
            "id": t.id, "title": t.title, "description": t.description,
            "status": t.status, "assigned_to": t.assigned_to,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "project_name": proj_name, "meeting_id": t.meeting_id,
            "created_at": t.created_at.isoformat(),
        })

    # Overdue tasks
    now = datetime.utcnow()
    ot_result = await db.execute(
        select(TaskModel)
        .join(MeetingModel, MeetingModel.id == TaskModel.meeting_id)
        .where(
            MeetingModel.tenant_id == tenant_id,
            TaskModel.due_date < now,
            TaskModel.status.not_in(["completed"]),
        ).limit(5)
    )
    overdue_tasks = [{
        "id": t.id, "title": t.title, "status": "overdue",
        "assigned_to": t.assigned_to, "meeting_id": t.meeting_id,
        "created_at": t.created_at.isoformat(),
    } for t in ot_result.scalars().all()]

    # Recent decisions
    d_result = await db.execute(
        select(DecisionModel, MeetingModel)
        .join(MeetingModel, MeetingModel.id == DecisionModel.meeting_id)
        .where(MeetingModel.tenant_id == tenant_id)
        .order_by(DecisionModel.created_at.desc()).limit(5)
    )
    recent_decisions = []
    for decision, meeting in d_result.fetchall():
        recent_decisions.append({
            "id": decision.id, "title": decision.title,
            "description": decision.description, "status": decision.status,
            "meeting_id": decision.meeting_id, "meeting_title": meeting.title,
            "project_name": None, "assigned_to": decision.assigned_to,
            "created_at": decision.created_at.isoformat(), "revision_count": 0,
        })

    # Active projects
    ap_result = await db.execute(
        select(ProjectModel)
        .join(EntityModel, EntityModel.id == ProjectModel.entity_id)
        .where(EntityModel.tenant_id == tenant_id, ProjectModel.status == "active")
        .limit(5)
    )
    active_projects = []
    for p in ap_result.scalars().all():
        m_count = (await db.execute(
            select(func.count(MeetingEntityModel.id))
            .join(EntityModel, EntityModel.id == MeetingEntityModel.entity_id)
            .where(EntityModel.id == p.entity_id)
        )).scalar() or 0
        active_projects.append({
            "id": p.id, "name": p.name, "description": p.description,
            "meeting_count": m_count, "status": p.status,
            "participant_count": 0, "decision_count": 0, "open_task_count": 0,
        })

    # Memory stats
    total_meetings = (
        await db.execute(select(func.count(MeetingModel.id)).where(MeetingModel.tenant_id == tenant_id))
    ).scalar() or 0
    total_entities = (
        await db.execute(select(func.count(EntityModel.id)).where(EntityModel.tenant_id == tenant_id))
    ).scalar() or 0
    tenant_meeting_ids = select(MeetingModel.id).where(MeetingModel.tenant_id == tenant_id)
    total_decisions = (
        await db.execute(
            select(func.count(DecisionModel.id)).where(DecisionModel.meeting_id.in_(tenant_meeting_ids))
        )
    ).scalar() or 0
    total_tasks = (
        await db.execute(
            select(func.count(TaskModel.id)).where(TaskModel.meeting_id.in_(tenant_meeting_ids))
        )
    ).scalar() or 0

    breakdown_result = await db.execute(
        select(EntityModel.type, func.count(EntityModel.id))
        .where(EntityModel.tenant_id == tenant_id)
        .group_by(EntityModel.type)
    )
    entity_breakdown = {row[0]: row[1] for row in breakdown_result.fetchall()}

    total_relationships = (
        await db.execute(
            select(func.count(EntityRelationshipModel.id)).where(
                EntityRelationshipModel.meeting_id.in_(tenant_meeting_ids)
            )
        )
    ).scalar() or 0

    memory_stats = MemoryStats(
        total_meetings=total_meetings,
        total_entities=total_entities,
        total_relationships=total_relationships,
        total_decisions=total_decisions,
        total_tasks=total_tasks,
        entity_breakdown=entity_breakdown,
        memory_size_mb=round(total_entities * 0.01 + total_relationships * 0.005, 2),
    )

    # Unresolved blockers
    b_result = await db.execute(
        select(EntityModel.name)
        .where(EntityModel.tenant_id == tenant_id, EntityModel.type == "blocker")
        .limit(5)
    )
    blockers = [row[0] for row in b_result.fetchall()]

    return DashboardData(
        recent_meetings=recent_meetings,
        pending_tasks=pending_tasks,
        recent_decisions=recent_decisions,
        active_projects=active_projects,
        memory_stats=memory_stats,
        unresolved_blockers=blockers,
        overdue_tasks=overdue_tasks,
    )


@router.get("/topics", response_model=List[TopicFrequency])
async def get_top_topics(
    limit: int = 10,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get most frequently discussed topics."""
    result = await db.execute(
        select(EntityModel.name, func.count(MeetingEntityModel.id).label("count"))
        .join(MeetingEntityModel, MeetingEntityModel.entity_id == EntityModel.id)
        .where(EntityModel.tenant_id == current_user.tenant_id, EntityModel.type == "topic")
        .group_by(EntityModel.name, EntityModel.last_seen)
        .order_by(desc("count"))
        .limit(limit)
    )
    rows = result.fetchall()

    return [
        TopicFrequency(
            topic=row[0],
            count=row[1],
            last_mentioned=datetime.utcnow() - timedelta(days=i),
            trend="stable",
        )
        for i, row in enumerate(rows)
    ]


@router.get("/activity", response_model=List[ActivityItem])
async def get_recent_activity(
    limit: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity feed."""
    result = await db.execute(
        select(ActivityLogModel)
        .where(ActivityLogModel.tenant_id == current_user.tenant_id)
        .order_by(ActivityLogModel.created_at.desc())
        .limit(limit)
    )
    activities = result.scalars().all()
    return [
        ActivityItem(
            id=str(a.id),
            type=a.type,
            title=a.title,
            description=a.description,
            timestamp=a.created_at,
            entity_id=a.entity_id,
            meeting_id=a.meeting_id,
        )
        for a in activities
    ]
