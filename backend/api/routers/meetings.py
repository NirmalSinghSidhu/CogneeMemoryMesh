from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime

from backend.database.connection import (
    get_db, MeetingModel, EntityModel, MeetingEntityModel,
    DecisionModel, TaskModel, ProjectModel
)
from backend.models.meeting import MeetingInput, MeetingResponse, MeetingDetailResponse, ProcessingStatusResponse
from backend.models.entity import EntityResponse
from backend.api.dependencies.auth import CurrentUser, get_current_user, get_meeting_for_tenant
from backend.services.meeting_service import meeting_service
from backend.utils.logger import logger

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _meeting_to_response(meeting: MeetingModel, participant_count: int = 0, entity_count: int = 0, project_names: List[str] = []) -> MeetingResponse:
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        date=meeting.date,
        status=meeting.status,
        participant_count=participant_count,
        entity_count=entity_count,
        project_names=project_names,
        summary=meeting.summary,
        duration_minutes=meeting.duration_minutes,
        tags=meeting.tags or [],
        created_at=meeting.created_at,
    )


@router.get("", response_model=List[MeetingResponse])
async def list_meetings(
    project_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(MeetingModel)
        .where(MeetingModel.tenant_id == current_user.tenant_id)
        .order_by(MeetingModel.date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    meetings = result.scalars().all()

    responses = []
    for m in meetings:
        # Count entities
        count_result = await db.execute(
            select(func.count(MeetingEntityModel.id)).where(MeetingEntityModel.meeting_id == m.id)
        )
        entity_count = count_result.scalar() or 0

        person_result = await db.execute(
            select(func.count(MeetingEntityModel.id))
            .join(EntityModel, EntityModel.id == MeetingEntityModel.entity_id)
            .where(and_(MeetingEntityModel.meeting_id == m.id, EntityModel.type == "person"))
        )
        participant_count = person_result.scalar() or 0

        # Get project names
        proj_result = await db.execute(
            select(EntityModel.name)
            .join(MeetingEntityModel, MeetingEntityModel.entity_id == EntityModel.id)
            .where(and_(MeetingEntityModel.meeting_id == m.id, EntityModel.type == "project"))
        )
        project_names = [r[0] for r in proj_result.fetchall()]

        responses.append(_meeting_to_response(m, participant_count, entity_count, project_names))

    return responses


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    data: MeetingInput,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = await meeting_service.create_meeting(
        db, data.model_dump(), tenant_id=current_user.tenant_id
    )
    await db.commit()
    await db.refresh(meeting)

    # Process in background
    background_tasks.add_task(_process_meeting_background, meeting.id)

    return _meeting_to_response(meeting)


async def _process_meeting_background(meeting_id: int):
    from backend.database.connection import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await meeting_service.process_meeting(db, meeting_id)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("Background processing failed for meeting %d: %s", meeting_id, str(e))


@router.get("/{id}", response_model=MeetingDetailResponse)
async def get_meeting(
    id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = await get_meeting_for_tenant(db, id, current_user.tenant_id)

    # Get entities grouped by type
    ents_result = await db.execute(
        select(EntityModel)
        .join(MeetingEntityModel, MeetingEntityModel.entity_id == EntityModel.id)
        .where(MeetingEntityModel.meeting_id == id)
    )
    entities = ents_result.scalars().all()

    # Count meeting appearances for each entity
    entity_responses = []
    for e in entities:
        count_result = await db.execute(
            select(func.count(MeetingEntityModel.id)).where(MeetingEntityModel.entity_id == e.id)
        )
        count = count_result.scalar() or 1
        entity_responses.append({
            "id": e.id,
            "name": e.name,
            "type": e.type,
            "description": e.description,
            "meeting_count": count,
            "first_seen": e.first_seen.isoformat() if e.first_seen else None,
            "last_seen": e.last_seen.isoformat() if e.last_seen else None,
        })

    # Get decisions
    dec_result = await db.execute(
        select(DecisionModel).where(DecisionModel.meeting_id == id)
    )
    decisions = dec_result.scalars().all()
    decision_responses = [{
        "id": d.id,
        "title": d.title,
        "description": d.description,
        "status": d.status,
        "meeting_id": d.meeting_id,
        "assigned_to": d.assigned_to,
        "created_at": d.created_at.isoformat(),
        "revision_count": 0,
    } for d in decisions]

    # Get tasks
    task_result = await db.execute(
        select(TaskModel).where(TaskModel.meeting_id == id)
    )
    tasks = task_result.scalars().all()
    task_responses = [{
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "assigned_to": t.assigned_to,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "meeting_id": t.meeting_id,
        "created_at": t.created_at.isoformat(),
    } for t in tasks]

    participants = [e for e in entity_responses if e["type"] == "person"]
    risks = [e["name"] for e in entity_responses if e["type"] == "risk"]
    blockers = [e["name"] for e in entity_responses if e["type"] == "blocker"]
    topics = [e["name"] for e in entity_responses if e["type"] == "topic"]

    return MeetingDetailResponse(
        id=meeting.id,
        title=meeting.title,
        date=meeting.date,
        status=meeting.status,
        transcript=meeting.transcript,
        summary=meeting.summary,
        entities=entity_responses,
        decisions=decision_responses,
        tasks=task_responses,
        participants=participants,
        risks=risks,
        blockers=blockers,
        topics=topics,
        related_meetings=[],
        duration_minutes=meeting.duration_minutes,
    )


@router.delete("/{id}", response_model=dict)
async def delete_meeting(
    id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_meeting_for_tenant(db, id, current_user.tenant_id)
    result = await meeting_service.forget_meeting(db, id, current_user.tenant_id)
    await db.commit()
    return result.model_dump()


@router.post("/{id}/process", response_model=ProcessingStatusResponse, status_code=202)
async def process_meeting(
    id: int,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_meeting_for_tenant(db, id, current_user.tenant_id)

    background_tasks.add_task(_process_meeting_background, id)
    return ProcessingStatusResponse(
        meeting_id=id,
        status="processing",
        message="Processing started",
        progress=0,
    )


@router.get("/{id}/entities", response_model=List[dict])
async def get_meeting_entities(
    id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_meeting_for_tenant(db, id, current_user.tenant_id)
    result = await db.execute(
        select(EntityModel)
        .join(MeetingEntityModel, MeetingEntityModel.entity_id == EntityModel.id)
        .where(MeetingEntityModel.meeting_id == id)
    )
    entities = result.scalars().all()
    return [{
        "id": e.id,
        "name": e.name,
        "type": e.type,
        "description": e.description,
        "meeting_count": 1,
        "first_seen": e.first_seen.isoformat() if e.first_seen else None,
        "last_seen": e.last_seen.isoformat() if e.last_seen else None,
    } for e in entities]
