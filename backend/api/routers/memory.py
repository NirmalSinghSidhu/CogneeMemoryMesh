from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete
from datetime import datetime
from typing import Optional

from backend.database.connection import (
    get_db, MeetingModel, EntityModel, MeetingEntityModel,
    EntityRelationshipModel, DecisionModel, TaskModel,
    ActivityLogModel, ProjectModel
)
from backend.services.cognee_service import cognee_service
from backend.services.meeting_service import meeting_service
from backend.models.memory import (
    RememberInput, RecallInput, ImproveInput, ForgetInput,
    MemoryResult, RecallResult, OperationResult, MemoryStats, ForgetScope,
    CogneeHealth,
)
from backend.api.dependencies.auth import (
    CurrentUser, get_current_user, get_meeting_for_tenant, tenant_dataset_name,
)
from backend.utils.config import settings

router = APIRouter(prefix="/memory", tags=["memory"])


def _require_cognee() -> None:
    if settings.cognee_required and not cognee_service.is_active:
        raise HTTPException(
            status_code=503,
            detail="Cognee is required but not available",
        )


@router.get("/health", response_model=CogneeHealth)
async def memory_health(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Cognee availability and dataset count."""
    return await cognee_service.health()


@router.post("/remember", response_model=MemoryResult)
async def remember_meeting(
    data: RememberInput,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cognee Remember() — store meeting in the knowledge graph."""
    _require_cognee()
    meeting = await get_meeting_for_tenant(db, data.meeting_id, current_user.tenant_id)

    if data.force_reindex:
        meeting.status = "pending"
        await db.flush()

    mem_result = await cognee_service.remember(
        text=meeting.transcript,
        dataset_name=tenant_dataset_name(current_user.tenant_id, meeting.id),
        meeting_id=meeting.id,
        metadata={"title": meeting.title, "date": str(meeting.date)},
    )
    if mem_result.success:
        meeting.status = "indexed"
    elif settings.cognee_required or cognee_service.is_active:
        meeting.status = "failed"
    await db.commit()
    return mem_result


@router.post("/recall", response_model=RecallResult)
async def recall_memory(
    data: RecallInput,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cognee Recall() — retrieve relevant memories for a query."""
    _require_cognee()
    result = await cognee_service.recall(query=data.query, limit=data.context_limit)
    return result


@router.post("/improve", response_model=MemoryResult)
async def improve_memory(
    data: ImproveInput,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cognee Improve() — update/evolve existing memories with new information."""
    _require_cognee()
    meeting = await get_meeting_for_tenant(db, data.meeting_id, current_user.tenant_id)

    e_result = await db.execute(
        select(EntityModel).where(
            EntityModel.id == data.target_entity_id,
            EntityModel.tenant_id == current_user.tenant_id,
        )
    )
    entity = e_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    result = await cognee_service.improve(
        new_text=cognee_service.format_remember_text(
            meeting.transcript,
            meeting.id,
            {"title": meeting.title, "date": str(meeting.date)},
        ),
        dataset_name=tenant_dataset_name(current_user.tenant_id, meeting.id),
        old_entity_name=entity.name,
        relationship_type=(
            data.relationship_type.value
            if hasattr(data.relationship_type, "value")
            else str(data.relationship_type)
        ),
        meeting_id=meeting.id,
    )

    db.add(ActivityLogModel(
        tenant_id=current_user.tenant_id,
        type="memory_improved",
        title=f"Memory improved: '{entity.name}'",
        description=f"Updated via {data.relationship_type} from meeting '{meeting.title}'",
        entity_id=entity.id,
        meeting_id=meeting.id,
    ))
    await db.commit()
    return result


@router.post("/forget", response_model=OperationResult)
async def forget_memory(
    data: ForgetInput,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cognee Forget() — remove memories from the graph."""
    _require_cognee()
    tenant_id = current_user.tenant_id

    if data.scope == ForgetScope.WORKSPACE:
        result = await cognee_service.forget(scope=ForgetScope.WORKSPACE)
        tenant_meeting_ids = (
            await db.execute(select(MeetingModel.id).where(MeetingModel.tenant_id == tenant_id))
        ).scalars().all()
        if tenant_meeting_ids:
            await db.execute(
                delete(ActivityLogModel).where(ActivityLogModel.tenant_id == tenant_id)
            )
            await db.execute(
                delete(DecisionModel).where(DecisionModel.meeting_id.in_(tenant_meeting_ids))
            )
            await db.execute(
                delete(TaskModel).where(TaskModel.meeting_id.in_(tenant_meeting_ids))
            )
            await db.execute(
                delete(MeetingEntityModel).where(MeetingEntityModel.meeting_id.in_(tenant_meeting_ids))
            )
            await db.execute(
                delete(EntityRelationshipModel).where(
                    EntityRelationshipModel.meeting_id.in_(tenant_meeting_ids)
                )
            )
            await db.execute(delete(EntityModel).where(EntityModel.tenant_id == tenant_id))
            await db.execute(delete(ProjectModel).where(
                ProjectModel.entity_id.in_(
                    select(EntityModel.id).where(EntityModel.tenant_id == tenant_id)
                )
            ))
            await db.execute(delete(MeetingModel).where(MeetingModel.tenant_id == tenant_id))
        await db.commit()
        return result

    elif data.scope == ForgetScope.MEETING and data.target_id:
        result = await meeting_service.forget_meeting(db, data.target_id, tenant_id)
        await db.commit()
        return result

    elif data.scope == ForgetScope.PROJECT and data.target_id:
        result = await meeting_service.forget_project(db, data.target_id, tenant_id)
        await db.commit()
        return result

    elif data.scope == ForgetScope.ENTITY and data.target_id:
        result = await meeting_service.forget_entity(db, data.target_id, tenant_id)
        await db.commit()
        return result

    raise HTTPException(status_code=400, detail="Invalid forget scope or missing target_id")


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get overall memory statistics."""
    tenant_id = current_user.tenant_id
    tenant_meeting_ids = select(MeetingModel.id).where(MeetingModel.tenant_id == tenant_id)

    total_meetings = (
        await db.execute(select(func.count(MeetingModel.id)).where(MeetingModel.tenant_id == tenant_id))
    ).scalar() or 0
    total_entities = (
        await db.execute(select(func.count(EntityModel.id)).where(EntityModel.tenant_id == tenant_id))
    ).scalar() or 0
    total_relationships = (
        await db.execute(
            select(func.count(EntityRelationshipModel.id)).where(
                EntityRelationshipModel.meeting_id.in_(tenant_meeting_ids)
            )
        )
    ).scalar() or 0
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

    last_meeting = (
        await db.execute(
            select(MeetingModel.created_at)
            .where(MeetingModel.tenant_id == tenant_id)
            .order_by(MeetingModel.created_at.desc())
            .limit(1)
        )
    ).scalar()

    return MemoryStats(
        total_meetings=total_meetings,
        total_entities=total_entities,
        total_relationships=total_relationships,
        total_decisions=total_decisions,
        total_tasks=total_tasks,
        entity_breakdown=entity_breakdown,
        memory_size_mb=round(total_entities * 0.01 + total_relationships * 0.005, 2),
        last_updated=last_meeting,
    )
