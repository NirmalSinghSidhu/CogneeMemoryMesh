from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional
from datetime import datetime

from backend.database.connection import (
    get_db, DecisionModel, DecisionHistoryModel, MeetingModel,
    ProjectModel, TaskModel, ActivityLogModel, EntityModel, MeetingEntityModel
)
from backend.models.entity import DecisionResponse, DecisionEvolutionResponse, DecisionHistoryEntry, TaskResponse
from backend.models.memory import TimelineEvent, OperationResult
from backend.api.dependencies.auth import CurrentUser, get_current_user
from backend.utils.logger import logger

router = APIRouter(tags=["decisions"])


@router.get("/decisions", response_model=List[DecisionResponse])
async def list_decisions(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tracked decisions."""
    query = (
        select(DecisionModel, MeetingModel)
        .join(MeetingModel)
        .where(MeetingModel.tenant_id == current_user.tenant_id)
    )
    if status:
        query = query.where(DecisionModel.status == status)
    if project_id:
        query = query.where(DecisionModel.project_id == project_id)
    query = query.order_by(DecisionModel.created_at.desc())

    result = await db.execute(query)
    rows = result.fetchall()

    decisions = []
    for decision, meeting in rows:
        # Count revisions
        rev_count = (await db.execute(
            select(func.count(DecisionHistoryModel.id))
            .where(DecisionHistoryModel.decision_id == decision.id)
        )).scalar() or 0

        proj_name = None
        if decision.project_id:
            proj = (await db.execute(
                select(ProjectModel).where(ProjectModel.id == decision.project_id)
            )).scalar_one_or_none()
            proj_name = proj.name if proj else None

        decisions.append(DecisionResponse(
            id=decision.id,
            title=decision.title,
            description=decision.description,
            status=decision.status,
            meeting_id=decision.meeting_id,
            meeting_title=meeting.title,
            project_name=proj_name,
            assigned_to=decision.assigned_to,
            created_at=decision.created_at,
            revision_count=max(0, rev_count - 1),
        ))

    return decisions


@router.get("/decisions/{id}/evolution", response_model=DecisionEvolutionResponse)
async def get_decision_evolution(
    id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    THE WOW FEATURE — Get the full evolution timeline of a decision.
    
    Shows how a decision changed across meetings:
    e.g., JWT → security_issues → Migration → OAuth
    """
    result = await db.execute(
        select(DecisionModel, MeetingModel)
        .join(MeetingModel, MeetingModel.id == DecisionModel.meeting_id)
        .where(DecisionModel.id == id, MeetingModel.tenant_id == current_user.tenant_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")

    decision, meeting = row

    # Get full history
    hist_result = await db.execute(
        select(DecisionHistoryModel, MeetingModel)
        .join(MeetingModel, MeetingModel.id == DecisionHistoryModel.meeting_id)
        .where(DecisionHistoryModel.decision_id == id)
        .order_by(DecisionHistoryModel.created_at.asc())
    )
    history_rows = hist_result.fetchall()

    history_entries = [
        DecisionHistoryEntry(
            meeting_id=h.meeting_id,
            meeting_title=m.title,
            date=h.created_at,
            action=h.action,
            description=h.description,
            previous_value=h.previous_value,
            new_value=h.new_value,
        )
        for h, m in history_rows
    ]

    # Build timeline events
    timeline = []
    for h, m in history_rows:
        timeline.append({
            "id": f"hist_{h.id}",
            "type": "decision" if h.action == "created" else "decision_update",
            "title": f"{h.action.title()}: {decision.title[:60]}",
            "description": h.description,
            "date": h.created_at.isoformat(),
            "meeting_id": h.meeting_id,
            "meeting_title": m.title,
            "entity_id": decision.id,
            "status": h.action,
            "is_milestone": h.action in ("created", "superseded", "implemented"),
        })

    proj_name = None
    if decision.project_id:
        proj = (await db.execute(
            select(ProjectModel).where(ProjectModel.id == decision.project_id)
        )).scalar_one_or_none()
        proj_name = proj.name if proj else None

    return DecisionEvolutionResponse(
        decision_id=decision.id,
        title=decision.title,
        current_status=decision.status,
        current_description=decision.description,
        project_name=proj_name,
        history=history_entries,
        timeline=timeline,
        pros=decision.pros or [],
        cons=decision.cons or [],
        reasons=decision.reasons or [],
    )


@router.get("/timeline", response_model=List[dict])
async def get_timeline(
    project_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chronological timeline of all events."""
    tenant_id = current_user.tenant_id
    events = []

    m_result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.tenant_id == tenant_id)
        .order_by(MeetingModel.date.desc())
        .limit(50)
    )
    for m in m_result.scalars().all():
        events.append({
            "id": f"meeting_{m.id}",
            "type": "meeting",
            "title": m.title,
            "description": m.summary,
            "date": m.date.isoformat(),
            "meeting_id": m.id,
            "meeting_title": m.title,
            "entity_id": None,
            "status": m.status,
            "project_name": None,
            "is_milestone": False,
        })

    # Decisions
    d_result = await db.execute(
        select(DecisionModel, MeetingModel)
        .join(MeetingModel)
        .where(MeetingModel.tenant_id == tenant_id)
        .order_by(DecisionModel.created_at.desc()).limit(50)
    )
    for d, m in d_result.fetchall():
        events.append({
            "id": f"decision_{d.id}",
            "type": "decision",
            "title": d.title,
            "description": d.description,
            "date": d.created_at.isoformat(),
            "meeting_id": m.id,
            "meeting_title": m.title,
            "entity_id": d.id,
            "status": d.status,
            "project_name": None,
            "is_milestone": d.status in ("implemented", "superseded"),
        })

    # Tasks
    t_result = await db.execute(
        select(TaskModel, MeetingModel)
        .join(MeetingModel)
        .where(MeetingModel.tenant_id == tenant_id)
        .order_by(TaskModel.created_at.desc()).limit(30)
    )
    for t, m in t_result.fetchall():
        events.append({
            "id": f"task_{t.id}",
            "type": "task",
            "title": t.title,
            "description": t.description,
            "date": t.created_at.isoformat(),
            "meeting_id": m.id,
            "meeting_title": m.title,
            "entity_id": t.id,
            "status": t.status,
            "project_name": None,
            "is_milestone": t.status == "completed",
        })

    # Sort by date desc
    events.sort(key=lambda x: x["date"], reverse=True)
    return events[:100]


@router.get("/entities", response_model=List[dict])
async def list_entities(
    type: Optional[str] = None,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all entities."""
    query = select(EntityModel).where(EntityModel.tenant_id == current_user.tenant_id)
    if type:
        query = query.where(EntityModel.type == type)
    query = query.order_by(EntityModel.last_seen.desc()).limit(limit)

    result = await db.execute(query)
    entities = result.scalars().all()

    responses = []
    for e in entities:
        count = (await db.execute(
            select(func.count(MeetingEntityModel.id)).where(MeetingEntityModel.entity_id == e.id)
        )).scalar() or 0
        responses.append({
            "id": e.id,
            "name": e.name,
            "type": e.type,
            "description": e.description,
            "meeting_count": count,
            "first_seen": e.first_seen.isoformat() if e.first_seen else None,
            "last_seen": e.last_seen.isoformat() if e.last_seen else None,
            "attributes": e.attributes or {},
        })
    return responses


@router.delete("/entities/{id}/forget", response_model=OperationResult)
async def forget_entity(
    id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forget a specific entity (SQL + best-effort Cognee)."""
    from backend.services.meeting_service import meeting_service

    result = await meeting_service.forget_entity(db, id, current_user.tenant_id)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    await db.commit()
    return result


@router.get("/projects", response_model=List[dict])
async def list_projects(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all projects."""
    result = await db.execute(
        select(ProjectModel)
        .join(EntityModel, EntityModel.id == ProjectModel.entity_id)
        .where(EntityModel.tenant_id == current_user.tenant_id)
    )
    projects = result.scalars().all()

    responses = []
    for p in projects:
        m_count = (await db.execute(
            select(func.count(MeetingEntityModel.id))
            .join(EntityModel, EntityModel.id == MeetingEntityModel.entity_id)
            .where(EntityModel.id == p.entity_id)
        )).scalar() or 0
        responses.append({
            "id": p.id, "name": p.name, "description": p.description,
            "meeting_count": m_count, "status": p.status,
            "participant_count": 0, "decision_count": 0, "open_task_count": 0,
        })
    return responses


@router.delete("/projects/{id}/forget", response_model=OperationResult)
async def forget_project(
    id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forget all memories related to a project."""
    from backend.services.meeting_service import meeting_service
    result = await meeting_service.forget_project(db, id, current_user.tenant_id)
    await db.commit()
    return result
