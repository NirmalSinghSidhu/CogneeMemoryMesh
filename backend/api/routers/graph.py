from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List

from backend.database.connection import (
    get_db, EntityModel, EntityRelationshipModel, MeetingEntityModel, MeetingModel
)
from backend.models.memory import GraphData, GraphNode, GraphNodeSummary, GraphEdge
from backend.api.dependencies.auth import CurrentUser, get_current_user
from backend.services.cognee_service import cognee_service
from backend.utils.config import settings
from backend.utils.logger import logger

router = APIRouter(prefix="/graph", tags=["graph"])

NODE_COLORS = {
    "person": "#06b6d4",
    "project": "#8b5cf6",
    "decision": "#f59e0b",
    "task": "#10b981",
    "topic": "#6366f1",
    "risk": "#ef4444",
    "blocker": "#f97316",
    "document": "#84cc16",
    "question": "#ec4899",
    "deadline": "#14b8a6",
    "meeting": "#3b82f6",
}


async def _sql_graph(
    db: AsyncSession,
    tenant_id: int,
    entity_type: Optional[str] = None,
) -> GraphData:
    """Postgres projection used when Cognee is inactive or empty."""
    query = select(EntityModel).where(EntityModel.tenant_id == tenant_id)
    if entity_type:
        query = query.where(EntityModel.type == entity_type)
    query = query.limit(200)

    result = await db.execute(query)
    entities = result.scalars().all()

    meetings_result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.tenant_id == tenant_id)
        .order_by(MeetingModel.date.desc())
        .limit(50)
    )
    meetings = meetings_result.scalars().all()

    nodes: List[GraphNodeSummary] = []
    node_ids = set()

    for entity in entities:
        count_result = await db.execute(
            select(func.count(MeetingEntityModel.id))
            .where(MeetingEntityModel.entity_id == entity.id)
        )
        meeting_count = count_result.scalar() or 1

        node_id = f"entity_{entity.id}"
        node_ids.add(node_id)
        nodes.append(GraphNodeSummary(
            id=node_id,
            label=entity.name,
            type=entity.type,
            weight=float(meeting_count),
            entity_id=entity.id,
            color=NODE_COLORS.get(entity.type, "#94a3b8"),
            description=entity.description,
        ))

    for meeting in meetings:
        node_id = f"meeting_{meeting.id}"
        node_ids.add(node_id)
        nodes.append(GraphNodeSummary(
            id=node_id,
            label=meeting.title,
            type="meeting",
            weight=2.0,
            entity_id=meeting.id,
            color=NODE_COLORS["meeting"],
            description=meeting.summary,
        ))

    tenant_meeting_ids = select(MeetingModel.id).where(MeetingModel.tenant_id == tenant_id)
    rel_result = await db.execute(
        select(EntityRelationshipModel)
        .where(EntityRelationshipModel.meeting_id.in_(tenant_meeting_ids))
        .limit(500)
    )
    relationships = rel_result.scalars().all()

    edges: List[GraphEdge] = []
    for rel in relationships:
        source_id = f"entity_{rel.source_id}"
        target_id = f"entity_{rel.target_id}"
        if source_id in node_ids and target_id in node_ids:
            edges.append(GraphEdge(
                source=source_id,
                target=target_id,
                relationship=rel.relationship,
                weight=rel.weight or 1.0,
                meeting_id=rel.meeting_id,
            ))

    me_result = await db.execute(
        select(MeetingEntityModel)
        .where(MeetingEntityModel.meeting_id.in_(tenant_meeting_ids))
        .limit(500)
    )
    meeting_entities = me_result.scalars().all()
    for me in meeting_entities:
        source_id = f"meeting_{me.meeting_id}"
        target_id = f"entity_{me.entity_id}"
        if source_id in node_ids and target_id in node_ids:
            edges.append(GraphEdge(
                source=source_id,
                target=target_id,
                relationship="contains",
                weight=1.0,
                meeting_id=me.meeting_id,
            ))

    return GraphData(
        nodes=nodes,
        edges=edges,
        node_count=len(nodes),
        edge_count=len(edges),
        source="sql",
    )


@router.get("", response_model=GraphData)
async def get_graph(
    project_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    depth: int = 3,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the knowledge graph — Cognee-first, SQL fallback."""
    if settings.cognee_required and not cognee_service.is_active:
        raise HTTPException(
            status_code=503,
            detail="Cognee is required but not available",
        )

    if cognee_service.is_active:
        cognee_graph = await cognee_service.get_graph(entity_type=entity_type)
        if cognee_graph is not None and (cognee_graph.nodes or settings.cognee_required):
            return cognee_graph
        if cognee_graph is not None and not cognee_graph.nodes:
            logger.info("Graph(): Cognee graph empty — falling back to SQL projection")

    if settings.cognee_required:
        return GraphData(nodes=[], edges=[], node_count=0, edge_count=0, source="cognee")

    return await _sql_graph(db, current_user.tenant_id, entity_type=entity_type)


@router.get("/node/{node_id}", response_model=GraphNode)
async def get_graph_node(
    node_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get node details with its connections — Cognee-first for non-SQL ids."""
    tenant_id = current_user.tenant_id

    # Legacy SQL entity nodes.
    if node_id.startswith("entity_"):
        entity_id = int(node_id.replace("entity_", ""))
        result = await db.execute(
            select(EntityModel).where(
                EntityModel.id == entity_id,
                EntityModel.tenant_id == tenant_id,
            )
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Node not found")

        rels_result = await db.execute(
            select(EntityRelationshipModel).where(
                (EntityRelationshipModel.source_id == entity_id) |
                (EntityRelationshipModel.target_id == entity_id)
            ).limit(50)
        )
        rels = rels_result.scalars().all()

        connections = [GraphEdge(
            source=f"entity_{r.source_id}",
            target=f"entity_{r.target_id}",
            relationship=r.relationship,
            weight=r.weight or 1.0,
            meeting_id=r.meeting_id,
        ) for r in rels]

        m_result = await db.execute(
            select(MeetingModel)
            .join(MeetingEntityModel, MeetingEntityModel.meeting_id == MeetingModel.id)
            .where(
                MeetingEntityModel.entity_id == entity_id,
                MeetingModel.tenant_id == tenant_id,
            )
            .limit(10)
        )
        meetings = m_result.scalars().all()

        return GraphNode(
            id=node_id,
            label=entity.name,
            type=entity.type,
            entity_id=entity.id,
            description=entity.description,
            connections=connections,
            meetings=[{
                "id": m.id,
                "title": m.title,
                "date": m.date.isoformat(),
                "status": m.status,
            } for m in meetings],
            attributes=entity.attributes or {},
        )

    # Meeting nodes from SQL projection.
    if node_id.startswith("meeting_"):
        meeting_id = int(node_id.replace("meeting_", ""))
        result = await db.execute(
            select(MeetingModel).where(
                MeetingModel.id == meeting_id,
                MeetingModel.tenant_id == tenant_id,
            )
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            raise HTTPException(status_code=404, detail="Node not found")

        me_result = await db.execute(
            select(MeetingEntityModel)
            .where(MeetingEntityModel.meeting_id == meeting_id)
            .limit(50)
        )
        connections = [
            GraphEdge(
                source=node_id,
                target=f"entity_{me.entity_id}",
                relationship="contains",
                weight=1.0,
                meeting_id=meeting_id,
            )
            for me in me_result.scalars().all()
        ]
        return GraphNode(
            id=node_id,
            label=meeting.title,
            type="meeting",
            entity_id=meeting.id,
            description=meeting.summary,
            connections=connections,
            meetings=[{
                "id": meeting.id,
                "title": meeting.title,
                "date": meeting.date.isoformat(),
                "status": meeting.status,
            }],
            attributes={},
        )

    # Cognee node ids (UUIDs / opaque strings).
    if cognee_service.is_active:
        node = await cognee_service.get_graph_node(node_id)
        if node:
            return node

    raise HTTPException(status_code=404, detail="Node not found")
