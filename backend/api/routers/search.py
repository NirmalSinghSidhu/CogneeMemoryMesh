from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List
from datetime import datetime

from backend.database.connection import (
    get_db, MeetingModel, EntityModel, DecisionModel, MeetingEntityModel
)
from backend.models.memory import SearchInput, SearchResult, SearchHit, TopicSuggestion, RecallItem
from backend.services.cognee_service import cognee_service
from backend.api.dependencies.auth import CurrentUser, get_current_user
from backend.utils.config import settings
from backend.utils.logger import logger

router = APIRouter(prefix="/search", tags=["search"])


def _require_cognee() -> None:
    if settings.cognee_required and not cognee_service.is_active:
        raise HTTPException(
            status_code=503,
            detail="Cognee is required but not available",
        )


def _recall_item_to_hit(item: RecallItem, index: int) -> SearchHit:
    return SearchHit(
        id=item.meeting_id or index,
        title=item.entity_name or item.meeting_title or "Memory",
        type="memory",
        score=item.relevance_score,
        excerpt=(item.content or "")[:300],
        meeting_id=item.meeting_id,
        meeting_title=item.meeting_title,
        date=item.date,
        entity_type=item.entity_type,
    )


async def _sql_keyword_search(
    db: AsyncSession,
    tenant_id: int,
    query: str,
    limit: int,
    entity_types: List[str],
) -> List[SearchHit]:
    results: List[SearchHit] = []
    score_base = 0.95
    q = query.lower()

    m_result = await db.execute(
        select(MeetingModel).where(
            MeetingModel.tenant_id == tenant_id,
            or_(
                func.lower(MeetingModel.title).contains(q),
                func.lower(MeetingModel.transcript).contains(q),
                func.lower(MeetingModel.summary).contains(q),
            ),
        ).limit(limit)
    )
    for meeting in m_result.scalars().all():
        title_match = q in meeting.title.lower()
        results.append(SearchHit(
            id=meeting.id,
            title=meeting.title,
            type="meeting",
            score=score_base if title_match else score_base - 0.2,
            excerpt=_get_excerpt(meeting.transcript or meeting.summary or "", q),
            meeting_id=meeting.id,
            meeting_title=meeting.title,
            date=meeting.date,
            entity_type=None,
        ))

    e_result = await db.execute(
        select(EntityModel).where(
            EntityModel.tenant_id == tenant_id,
            or_(
                func.lower(EntityModel.name).contains(q),
                func.lower(EntityModel.description).contains(q),
            ),
        ).limit(limit)
    )
    for entity in e_result.scalars().all():
        if entity_types and entity.type not in entity_types:
            continue
        me_result = await db.execute(
            select(MeetingModel)
            .join(MeetingEntityModel, MeetingEntityModel.meeting_id == MeetingModel.id)
            .where(MeetingEntityModel.entity_id == entity.id)
            .order_by(MeetingModel.date.desc())
            .limit(1)
        )
        meeting = me_result.scalar_one_or_none()
        results.append(SearchHit(
            id=entity.id,
            title=entity.name,
            type="entity",
            score=score_base - 0.1,
            excerpt=entity.description or f"{entity.type}: {entity.name}",
            meeting_id=meeting.id if meeting else None,
            meeting_title=meeting.title if meeting else None,
            date=meeting.date if meeting else None,
            entity_type=entity.type,
        ))

    d_result = await db.execute(
        select(DecisionModel, MeetingModel).join(MeetingModel)
        .where(
            MeetingModel.tenant_id == tenant_id,
            or_(
                func.lower(DecisionModel.title).contains(q),
                func.lower(DecisionModel.description).contains(q),
            ),
        ).limit(limit)
    )
    for decision, meeting in d_result.fetchall():
        results.append(SearchHit(
            id=decision.id,
            title=decision.title,
            type="decision",
            score=score_base - 0.05,
            excerpt=decision.description or decision.title,
            meeting_id=meeting.id,
            meeting_title=meeting.title,
            date=meeting.date,
            entity_type="decision",
        ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results


@router.post("", response_model=SearchResult)
async def search_memory(
    data: SearchInput,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cognee-first search; SQL keyword is fallback/secondary fill only."""
    _require_cognee()
    tenant_id = current_user.tenant_id
    mode = (data.mode or "hybrid").lower()
    results: List[SearchHit] = []

    if cognee_service.is_active:
        try:
            cognee_result = await cognee_service.recall(
                query=data.query,
                limit=data.limit,
                mode=mode,
            )
            for i, item in enumerate(cognee_result.results):
                results.append(_recall_item_to_hit(item, i))
        except Exception as e:
            logger.warning("Cognee search failed: %s", str(e))

    # Hybrid: fill remaining slots with SQL keyword hits.
    # Other modes: SQL only when Cognee inactive or returned nothing (and not required).
    need_sql = False
    if mode == "hybrid" and len(results) < data.limit:
        need_sql = True
    elif not results and not settings.cognee_required:
        need_sql = True

    if need_sql:
        sql_hits = await _sql_keyword_search(
            db, tenant_id, data.query, data.limit, data.entity_types or []
        )
        seen = {(h.type, h.id, h.title) for h in results}
        for hit in sql_hits:
            key = (hit.type, hit.id, hit.title)
            if key in seen:
                continue
            results.append(hit)
            seen.add(key)
            if len(results) >= data.limit:
                break

    results.sort(key=lambda x: x.score, reverse=True)
    return SearchResult(
        query=data.query,
        results=results[: data.limit],
        total=len(results),
        search_mode=mode,
    )


@router.get("/suggestions", response_model=List[TopicSuggestion])
async def get_search_suggestions(
    topic: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get real-time topic suggestions — detect conflicts and related meetings."""
    tenant_id = current_user.tenant_id
    topic_lower = topic.lower()

    result = await db.execute(
        select(EntityModel).where(
            EntityModel.tenant_id == tenant_id,
            func.lower(EntityModel.name).contains(topic_lower),
        ).limit(5)
    )
    entities = result.scalars().all()

    suggestions = []
    for entity in entities:
        m_result = await db.execute(
            select(MeetingModel)
            .join(MeetingEntityModel, MeetingEntityModel.meeting_id == MeetingModel.id)
            .where(
                MeetingEntityModel.entity_id == entity.id,
                MeetingModel.tenant_id == tenant_id,
            )
            .order_by(MeetingModel.date.desc())
            .limit(5)
        )
        meetings = m_result.scalars().all()
        meeting_titles = [m.title for m in meetings]
        last_discussed = meetings[0].date if meetings else datetime.utcnow()

        conflict_warning = None
        dec_result = await db.execute(
            select(DecisionModel)
            .join(MeetingModel, MeetingModel.id == DecisionModel.meeting_id)
            .where(
                MeetingModel.tenant_id == tenant_id,
                func.lower(DecisionModel.title).contains(entity.name.lower()),
                DecisionModel.status.in_(["active", "superseded"]),
            )
        )
        conflicting = dec_result.scalars().all()
        if len(conflicting) > 1:
            conflict_warning = f"Conflicting decisions exist for '{entity.name}' — review before deciding"

        suggestions.append(TopicSuggestion(
            topic=entity.name,
            related_meetings=meeting_titles,
            last_discussed=last_discussed,
            conflict_warning=conflict_warning,
            meeting_count=len(meeting_titles),
        ))

    return suggestions


def _get_excerpt(text: str, query: str, window: int = 200) -> str:
    """Extract a relevant excerpt containing the query."""
    if not text:
        return ""
    lower_text = text.lower()
    idx = lower_text.find(query)
    if idx == -1:
        return text[:window]
    start = max(0, idx - window // 2)
    end = min(len(text), idx + window // 2)
    return ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")
