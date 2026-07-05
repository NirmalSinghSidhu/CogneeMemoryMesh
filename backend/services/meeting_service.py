"""
Meeting Service

Orchestrates the full meeting ingestion pipeline:
1. Parse and store the meeting
2. Extract entities (via LLM or pattern matching)
3. Cognee Remember() — store in knowledge graph
4. Build entity relationships
5. Detect decision evolution (Improve())
6. Log activity
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.orm import selectinload

from backend.database.connection import (
    MeetingModel, EntityModel, MeetingEntityModel, EntityRelationshipModel,
    ProjectModel, DecisionModel, DecisionHistoryModel, TaskModel,
    ActivityLogModel, ChatMessageModel
)
from backend.services.cognee_service import cognee_service
from backend.services.extraction_service import extraction_service
from backend.models.memory import ForgetScope, OperationResult
from backend.api.dependencies.auth import tenant_dataset_name
from backend.utils.config import settings
from backend.utils.logger import logger


ENTITY_NODE_COLORS = {
    "person": "#06b6d4",    # cyan
    "project": "#8b5cf6",   # violet
    "decision": "#f59e0b",  # amber
    "task": "#10b981",      # green
    "topic": "#6366f1",     # indigo
    "risk": "#ef4444",      # red
    "blocker": "#f97316",   # orange
    "document": "#84cc16",  # lime
    "question": "#ec4899",  # pink
    "deadline": "#14b8a6",  # teal
}


class MeetingService:

    async def create_meeting(
        self, db: AsyncSession, data: Dict[str, Any], tenant_id: int
    ) -> MeetingModel:
        """Create a meeting record and immediately start processing."""
        meeting = MeetingModel(
            tenant_id=tenant_id,
            title=data["title"],
            date=data["date"],
            transcript=data["content"],
            content_type=data.get("content_type", "transcript"),
            duration_minutes=data.get("duration_minutes"),
            tags=data.get("tags", []),
            status="pending",
        )
        db.add(meeting)
        await db.flush()
        await db.refresh(meeting)

        # Log activity
        activity = ActivityLogModel(
            tenant_id=tenant_id,
            type="meeting_added",
            title=f"Meeting added: {meeting.title}",
            description=f"Processing started for '{meeting.title}'",
            meeting_id=meeting.id,
        )
        db.add(activity)
        await db.flush()

        return meeting

    async def process_meeting(self, db: AsyncSession, meeting_id: int) -> None:
        """
        Full ingestion pipeline for a meeting.
        Called asynchronously after creation.
        """
        result = await db.execute(select(MeetingModel).where(MeetingModel.id == meeting_id))
        meeting = result.scalar_one_or_none()
        if not meeting:
            return

        meeting.status = "processing"
        await db.flush()

        try:
            # 1. Extract entities
            extracted = await extraction_service.extract_from_transcript(meeting.transcript)

            # 2. Update summary
            if extracted.get("summary"):
                meeting.summary = extracted["summary"]

            # 3. Store entities and relationships
            entity_ids = await self._store_entities(db, meeting, extracted)

            # 4. Cognee Remember() — store in memory graph
            dataset_name = tenant_dataset_name(meeting.tenant_id, meeting.id)
            mem_result = await cognee_service.remember(
                text=meeting.transcript,
                dataset_name=dataset_name,
                meeting_id=meeting.id,
                metadata={"title": meeting.title, "date": str(meeting.date)},
            )

            if not mem_result.success:
                if settings.cognee_required or cognee_service.is_active:
                    meeting.status = "failed"
                    logger.error(
                        "Meeting %d Remember() failed: %s",
                        meeting_id,
                        mem_result.message,
                    )
                    await db.flush()
                    return
                logger.warning(
                    "Meeting %d continuing without Cognee: %s",
                    meeting_id,
                    mem_result.message,
                )

            # 5. Detect and link decision evolution (Improve)
            await self._detect_decision_evolution(db, meeting, extracted)

            # 6. Store decisions and tasks
            await self._store_decisions(db, meeting, extracted.get("decisions", []))
            await self._store_tasks(db, meeting, extracted.get("tasks", []))

            meeting.status = "indexed"
            logger.info("Meeting %d processed successfully", meeting_id)

        except Exception as e:
            meeting.status = "failed"
            logger.error("Meeting %d processing failed: %s", meeting_id, str(e))
            raise

        await db.flush()

    async def _store_entities(
        self,
        db: AsyncSession,
        meeting: MeetingModel,
        extracted: Dict[str, Any]
    ) -> Dict[str, List[int]]:
        """Store extracted entities, deduplicating against existing ones."""
        entity_ids: Dict[str, List[int]] = {}

        type_map = {
            "participants": "person",
            "projects": "project",
            "topics": "topic",
            "risks": "risk",
            "blockers": "blocker",
            "documents": "document",
            "questions": "question",
        }

        for field, entity_type in type_map.items():
            names = extracted.get(field, [])
            if not isinstance(names, list):
                continue
            for name in names:
                name = (name if isinstance(name, str) else str(name)).strip()
                if not name:
                    continue
                entity = await self._upsert_entity(db, name, entity_type, meeting.date, meeting.tenant_id)
                await self._link_entity_to_meeting(db, meeting.id, entity.id)
                entity_ids.setdefault(entity_type, []).append(entity.id)

                # Upsert project record
                if entity_type == "project":
                    await self._upsert_project(db, entity)

        # Build participant → project relationships
        participant_ids = entity_ids.get("person", [])
        project_ids = entity_ids.get("project", [])
        for p_id in participant_ids:
            for proj_id in project_ids:
                await self._upsert_relationship(
                    db, p_id, proj_id, "contributes_to", meeting.id
                )

        return entity_ids

    async def _upsert_entity(
        self,
        db: AsyncSession,
        name: str,
        entity_type: str,
        meeting_date: datetime,
        tenant_id: int,
    ) -> EntityModel:
        """Find existing entity by name+type or create new one."""
        result = await db.execute(
            select(EntityModel).where(
                and_(
                    func.lower(EntityModel.name) == name.lower(),
                    EntityModel.type == entity_type,
                    EntityModel.is_canonical == True,
                    EntityModel.tenant_id == tenant_id,
                )
            )
        )
        entity = result.scalar_one_or_none()

        if entity:
            entity.last_seen = meeting_date
        else:
            entity = EntityModel(
                tenant_id=tenant_id,
                name=name,
                type=entity_type,
                first_seen=meeting_date,
                last_seen=meeting_date,
                is_canonical=True,
            )
            db.add(entity)
            await db.flush()

        return entity

    async def _upsert_project(self, db: AsyncSession, entity: EntityModel) -> None:
        """Create a project record for a project entity."""
        result = await db.execute(
            select(ProjectModel).where(ProjectModel.entity_id == entity.id)
        )
        project = result.scalar_one_or_none()
        if not project:
            project = ProjectModel(
                entity_id=entity.id,
                name=entity.name,
                status="active",
            )
            db.add(project)
            await db.flush()

    async def _link_entity_to_meeting(
        self, db: AsyncSession, meeting_id: int, entity_id: int
    ) -> None:
        """Link entity to meeting or increment mention count."""
        result = await db.execute(
            select(MeetingEntityModel).where(
                and_(
                    MeetingEntityModel.meeting_id == meeting_id,
                    MeetingEntityModel.entity_id == entity_id,
                )
            )
        )
        link = result.scalar_one_or_none()
        if link:
            link.mention_count = (link.mention_count or 0) + 1
        else:
            link = MeetingEntityModel(
                meeting_id=meeting_id,
                entity_id=entity_id,
                mention_count=1,
            )
            db.add(link)

    async def _upsert_relationship(
        self,
        db: AsyncSession,
        source_id: int,
        target_id: int,
        relationship: str,
        meeting_id: int,
        weight: float = 1.0,
    ) -> None:
        """Create or strengthen an entity relationship."""
        result = await db.execute(
            select(EntityRelationshipModel).where(
                and_(
                    EntityRelationshipModel.source_id == source_id,
                    EntityRelationshipModel.target_id == target_id,
                    EntityRelationshipModel.relationship == relationship,
                )
            )
        )
        rel = result.scalar_one_or_none()
        if rel:
            rel.weight = min(10.0, (rel.weight or 1.0) + 0.5)
        else:
            rel = EntityRelationshipModel(
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                weight=weight,
                meeting_id=meeting_id,
            )
            db.add(rel)

    async def _store_decisions(
        self,
        db: AsyncSession,
        meeting: MeetingModel,
        decisions: List[Dict],
    ) -> None:
        """Store extracted decisions."""
        for d in decisions:
            if not d.get("title"):
                continue

            # Get project association
            project_id = await self._find_project_id(db, meeting.id)

            decision = DecisionModel(
                title=d["title"][:500],
                description=d.get("description"),
                status="active",
                meeting_id=meeting.id,
                project_id=project_id,
                assigned_to=d.get("assigned_to"),
                pros=d.get("pros", []),
                cons=d.get("cons", []),
                reasons=d.get("reasons", []),
            )
            db.add(decision)
            await db.flush()

            # Initial history entry
            history = DecisionHistoryModel(
                decision_id=decision.id,
                meeting_id=meeting.id,
                action="created",
                description=d.get("description", d["title"]),
                new_value=d.get("description"),
            )
            db.add(history)

            # Log activity
            db.add(ActivityLogModel(
                type="decision_made",
                title=f"Decision: {d['title'][:200]}",
                description=f"Decision made in '{meeting.title}'",
                meeting_id=meeting.id,
            ))

    async def _store_tasks(
        self,
        db: AsyncSession,
        meeting: MeetingModel,
        tasks: List[Dict],
    ) -> None:
        """Store extracted tasks."""
        for t in tasks:
            if not t.get("title"):
                continue
            project_id = await self._find_project_id(db, meeting.id)

            task = TaskModel(
                title=t["title"][:500],
                description=t.get("description"),
                status=t.get("status", "open"),
                assigned_to=t.get("assigned_to"),
                meeting_id=meeting.id,
                project_id=project_id,
            )
            db.add(task)
            await db.flush()

            db.add(ActivityLogModel(
                type="task_created",
                title=f"Task: {t['title'][:200]}",
                meeting_id=meeting.id,
            ))

    async def _find_project_id(self, db: AsyncSession, meeting_id: int) -> Optional[int]:
        """Find the first project associated with a meeting."""
        result = await db.execute(
            select(ProjectModel)
            .join(EntityModel, ProjectModel.entity_id == EntityModel.id)
            .join(MeetingEntityModel, MeetingEntityModel.entity_id == EntityModel.id)
            .where(MeetingEntityModel.meeting_id == meeting_id)
            .limit(1)
        )
        project = result.scalar_one_or_none()
        return project.id if project else None

    async def _detect_decision_evolution(
        self,
        db: AsyncSession,
        meeting: MeetingModel,
        extracted: Dict,
    ) -> None:
        """
        Implement Cognee Improve() — detect when new decisions update old ones.
        
        Pattern: if a new decision mentions existing entities (e.g., "JWT", "OAuth"),
        link them as an evolution chain and update the old decision's status.
        """
        new_decisions = extracted.get("decisions", [])
        if not new_decisions:
            return

        for new_decision in new_decisions:
            title = new_decision.get("title", "").lower()
            desc = new_decision.get("description", "").lower()
            combined = f"{title} {desc}"

            # Keywords suggesting a decision supersedes a previous one
            supersede_keywords = [
                "instead of", "replace", "migration", "migrate from",
                "switch from", "no longer", "deprecated", "moving from",
                "updated from", "changed from",
            ]

            if not any(kw in combined for kw in supersede_keywords):
                continue

            # Find potentially related existing decisions
            result = await db.execute(
                select(DecisionModel)
                .where(DecisionModel.meeting_id != meeting.id)
                .where(DecisionModel.status == "active")
                .limit(50)
            )
            old_decisions = result.scalars().all()

            for old in old_decisions:
                old_words = set(old.title.lower().split())
                new_words = set(title.split())
                overlap = len(old_words & new_words)

                if overlap >= 2:
                    # This new decision evolves/supersedes the old one
                    old.status = "superseded"

                    history = DecisionHistoryModel(
                        decision_id=old.id,
                        meeting_id=meeting.id,
                        action="superseded",
                        description=f"Superseded by: {new_decision['title']}",
                        previous_value=old.description,
                        new_value=new_decision.get("description"),
                    )
                    db.add(history)

                    # Cognee Improve() — link in memory graph
                    dataset_name = tenant_dataset_name(meeting.tenant_id, meeting.id)
                    await cognee_service.improve(
                        new_text=f"Decision '{new_decision['title']}' supersedes '{old.title}'",
                        dataset_name=dataset_name,
                        old_entity_name=old.title,
                        relationship_type="supersedes",
                        meeting_id=meeting.id,
                    )

                    db.add(ActivityLogModel(
                        tenant_id=meeting.tenant_id,
                        type="decision_updated",
                        title=f"Decision evolved: {old.title[:200]}",
                        description=f"Superseded in meeting '{meeting.title}'",
                        meeting_id=meeting.id,
                    ))

                    logger.info(
                        "Improve(): Decision '%s' superseded by '%s'",
                        old.title, new_decision["title"]
                    )

    async def forget_meeting(self, db: AsyncSession, meeting_id: int, tenant_id: int) -> OperationResult:
        """Forget a meeting — remove from DB and Cognee memory graph."""
        result = await db.execute(
            select(MeetingModel).where(
                MeetingModel.id == meeting_id,
                MeetingModel.tenant_id == tenant_id,
            )
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            return OperationResult(success=False, message="Meeting not found")

        dataset_name = tenant_dataset_name(tenant_id, meeting_id)
        await cognee_service.forget(scope=ForgetScope.MEETING, dataset_name=dataset_name)

        await db.delete(meeting)
        return OperationResult(
            success=True,
            message=f"Meeting '{meeting.title}' and all related memories removed",
            affected_count=1,
        )

    async def forget_project(self, db: AsyncSession, project_id: int, tenant_id: int) -> OperationResult:
        """Forget an entire project — all meetings, entities, decisions."""
        result = await db.execute(
            select(ProjectModel, EntityModel)
            .join(EntityModel, EntityModel.id == ProjectModel.entity_id)
            .where(
                ProjectModel.id == project_id,
                EntityModel.tenant_id == tenant_id,
            )
        )
        row = result.first()
        if not row:
            return OperationResult(success=False, message="Project not found")
        project, entity = row

        # Cognee Forget() for project
        await cognee_service.forget(
            scope=ForgetScope.PROJECT,
            dataset_name=project.name,
        )

        # Delete project entity and cascade
        if entity:
            await db.delete(entity)

        await db.delete(project)
        return OperationResult(
            success=True,
            message=f"Project '{project.name}' and all related memories removed",
            affected_count=1,
        )

    async def forget_entity(self, db: AsyncSession, entity_id: int, tenant_id: int) -> OperationResult:
        """Forget a single entity from SQL and best-effort Cognee prune by name."""
        result = await db.execute(
            select(EntityModel).where(
                EntityModel.id == entity_id,
                EntityModel.tenant_id == tenant_id,
            )
        )
        entity = result.scalar_one_or_none()
        if not entity:
            return OperationResult(success=False, message="Entity not found")

        name = entity.name
        # Best-effort: prune any Cognee datasets whose name mentions this entity.
        if cognee_service.is_active:
            await cognee_service.forget(scope=ForgetScope.PROJECT, dataset_name=name)

        await db.execute(
            delete(EntityRelationshipModel).where(
                or_(
                    EntityRelationshipModel.source_id == entity_id,
                    EntityRelationshipModel.target_id == entity_id,
                )
            )
        )
        await db.execute(
            delete(MeetingEntityModel).where(MeetingEntityModel.entity_id == entity_id)
        )
        await db.delete(entity)
        return OperationResult(
            success=True,
            message=f"Entity '{name}' removed from memory",
            affected_count=1,
        )


meeting_service = MeetingService()
