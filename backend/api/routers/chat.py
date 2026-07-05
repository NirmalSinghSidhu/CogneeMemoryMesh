from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from typing import List
from datetime import datetime
import uuid
import json

from backend.database.connection import (
    get_db, ChatMessageModel, MeetingModel, DecisionModel,
)
from backend.models.memory import ChatInput, ChatResponse, ChatMessage, MemorySource, RecallItem
from backend.services.llm_service import get_active_provider, stream_llm, PROVIDER_MODELS
from backend.services.cognee_service import cognee_service
from backend.api.dependencies.auth import CurrentUser, get_current_user
from backend.utils.config import settings
from backend.utils.logger import logger

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = """You are MemoryMesh, an AI assistant with access to an organization's meeting memory.
You help users recall decisions, understand project context, and explore what was discussed in past meetings.
Be concise, cite specific meetings and decisions when relevant, and format responses clearly using markdown.
If the context doesn't contain relevant information, say so honestly."""


async def _sql_fallback_context(
    db: AsyncSession, message: str, context_limit: int, tenant_id: int
) -> tuple[list, list]:
    query = message.lower()
    m_result = await db.execute(
        select(MeetingModel).where(
            MeetingModel.tenant_id == tenant_id,
            or_(
                func.lower(MeetingModel.title).contains(query),
                func.lower(MeetingModel.transcript).contains(query),
                func.lower(MeetingModel.summary).contains(query),
            ),
        ).limit(context_limit)
    )
    meetings = m_result.scalars().all()

    d_result = await db.execute(
        select(DecisionModel)
        .join(MeetingModel, MeetingModel.id == DecisionModel.meeting_id)
        .where(
            MeetingModel.tenant_id == tenant_id,
            or_(
                func.lower(DecisionModel.title).contains(query),
                func.lower(DecisionModel.description).contains(query),
            ),
        ).limit(4)
    )
    decisions = d_result.scalars().all()
    return meetings, decisions


def _build_recall_context_block(items: list[RecallItem]) -> str:
    if not items:
        return ""
    parts = ["## Relevant Memories (Cognee Recall)"]
    for i, item in enumerate(items, 1):
        title = item.meeting_title or item.entity_name or f"Memory {i}"
        parts.append(f"### {title}")
        if item.entity_type and item.entity_type != "unknown":
            parts.append(f"Type: {item.entity_type}")
        parts.append(item.content[:800])
    return f"\n\n---\n## Organizational Memory Context\n" + "\n".join(parts) + "\n---"


def _build_sql_context_block(meetings: list, decisions: list) -> str:
    parts: list[str] = []
    if meetings:
        parts.append("## Relevant Meetings")
        for m in meetings:
            date_str = m.date.strftime("%B %d, %Y")
            parts.append(f"### {m.title} ({date_str})")
            if m.summary:
                parts.append(m.summary)
            elif m.transcript:
                parts.append(m.transcript[:600])
    if decisions:
        parts.append("## Related Decisions")
        for d in decisions:
            parts.append(f"- **{d.title}** [{d.status.upper()}]: {d.description or ''}")
    if not parts:
        return ""
    return f"\n\n---\n## Organizational Memory Context\n" + "\n".join(parts) + "\n---"


def _format_recall_sources(items: list[RecallItem]) -> list[MemorySource]:
    sources: list[MemorySource] = []
    for item in items:
        if not item.meeting_id:
            continue
        sources.append(
            MemorySource(
                meeting_id=item.meeting_id,
                meeting_title=item.meeting_title or item.entity_name or "Memory",
                date=item.date or datetime.utcnow(),
                entity_type=item.entity_type or "memory",
                entity_name=item.entity_name or item.meeting_title or "Memory",
            )
        )
    return sources


def _format_meeting_sources(meetings: list) -> list[MemorySource]:
    return [
        MemorySource(
            meeting_id=m.id,
            meeting_title=m.title,
            date=m.date,
            entity_type="meeting",
            entity_name=m.title,
        )
        for m in meetings
    ]


async def _gather_chat_context(
    db: AsyncSession, message: str, context_limit: int, tenant_id: int
) -> tuple[str, list[MemorySource], list, list]:
    """Return (context_block, sources, meetings_for_response, decisions)."""
    if settings.cognee_required and not cognee_service.is_active:
        raise HTTPException(
            status_code=503,
            detail="Cognee is required but not available",
        )

    if cognee_service.is_active:
        recall = await cognee_service.recall(
            query=message, limit=context_limit, mode="hybrid"
        )
        if recall.results:
            return (
                _build_recall_context_block(recall.results),
                _format_recall_sources(recall.results),
                [],
                [],
            )

    if settings.cognee_required:
        return "", [], [], []

    meetings, decisions = await _sql_fallback_context(
        db, message, context_limit, tenant_id
    )
    return (
        _build_sql_context_block(meetings, decisions),
        _format_meeting_sources(meetings),
        meetings,
        decisions,
    )


def _sources_to_json(sources: list[MemorySource]) -> list[dict]:
    return [s.model_dump(mode="json") for s in sources]


def _format_decisions(decisions: list) -> list[dict]:
    return [{"id": d.id, "title": d.title, "status": d.status} for d in decisions]


@router.post("/stream")
async def chat_stream(
    data: ChatInput,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming chat — matches Node.js /api/chat/stream contract."""
    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    conversation_id = data.conversation_id or str(uuid.uuid4())
    provider = get_active_provider()
    context_limit = data.context_limit or 8

    context_block, sources, meetings, decisions = await _gather_chat_context(
        db, data.message, context_limit, current_user.tenant_id
    )

    prior_result = await db.execute(
        select(ChatMessageModel)
        .where(
            ChatMessageModel.conversation_id == conversation_id,
            ChatMessageModel.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(ChatMessageModel.created_at))
        .limit(10)
    )
    prior_messages = list(reversed(prior_result.scalars().all()))

    llm_messages = [
        {"role": m.role, "content": m.content}
        for m in prior_messages
    ]
    llm_messages.append({"role": "user", "content": data.message + context_block})

    db.add(ChatMessageModel(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation_id,
        role="user",
        content=data.message,
        sources_json=[],
    ))
    await db.commit()

    sources_json = _sources_to_json(sources)
    decisions_referenced = _format_decisions(decisions)

    async def event_stream():
        full_response = ""
        try:
            yield f"data: {json.dumps({'provider': provider, 'conversation_id': conversation_id})}\n\n"

            async for chunk in stream_llm(provider, llm_messages, SYSTEM_PROMPT):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            db.add(ChatMessageModel(
                tenant_id=current_user.tenant_id,
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                sources_json=sources_json,
            ))
            await db.commit()

            yield f"data: {json.dumps({'done': True, 'sources': sources_json, 'decisions_referenced': decisions_referenced, 'conversation_id': conversation_id})}\n\n"

        except Exception as e:
            logger.error("Chat stream failed: %s", str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Conversation-Id": conversation_id,
        },
    )


@router.post("", response_model=ChatResponse)
async def chat_with_memory(
    data: ChatInput,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming chat — backwards-compatible JSON response."""
    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    conversation_id = data.conversation_id or str(uuid.uuid4())
    provider = get_active_provider()
    context_limit = data.context_limit or 8

    context_block, sources, meetings, decisions = await _gather_chat_context(
        db, data.message, context_limit, current_user.tenant_id
    )
    llm_messages = [{"role": "user", "content": data.message + context_block}]

    full_response = ""
    async for chunk in stream_llm(provider, llm_messages, SYSTEM_PROMPT):
        full_response += chunk

    decisions_referenced = [
        {"id": d.id, "title": d.title, "status": d.status, "meeting_id": d.meeting_id, "revision_count": 0}
        for d in decisions
    ]
    meetings_referenced = [
        {
            "id": m.id,
            "title": m.title,
            "date": m.date.isoformat() if hasattr(m.date, "isoformat") else str(m.date),
            "status": m.status,
            "participant_count": 0,
            "entity_count": 0,
            "project_names": [],
            "tags": m.tags or [],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in meetings
    ]
    if not meetings_referenced and sources:
        meetings_referenced = [
            {
                "id": s.meeting_id,
                "title": s.meeting_title,
                "date": s.date.isoformat() if hasattr(s.date, "isoformat") else str(s.date),
                "status": "indexed",
                "participant_count": 0,
                "entity_count": 0,
                "project_names": [],
                "tags": [],
                "created_at": None,
            }
            for s in sources
        ]

    db.add(ChatMessageModel(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation_id,
        role="user",
        content=data.message,
        sources_json=[],
    ))
    db.add(ChatMessageModel(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation_id,
        role="assistant",
        content=full_response,
        sources_json=_sources_to_json(sources),
    ))
    await db.commit()

    return ChatResponse(
        answer=full_response,
        conversation_id=conversation_id,
        sources=sources,
        decisions_referenced=decisions_referenced,
        people_referenced=[],
        meetings_referenced=meetings_referenced,
        confidence=0.9 if (meetings or sources) else 0.5,
    )


@router.get("/history", response_model=List[ChatMessage])
async def get_chat_history(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.tenant_id == current_user.tenant_id)
        .order_by(ChatMessageModel.created_at.desc())
        .limit(50)
    )
    messages = result.scalars().all()
    return [
        ChatMessage(
            id=str(m.id),
            role=m.role,
            content=m.content,
            sources=m.sources_json or [],
            conversation_id=m.conversation_id,
            created_at=m.created_at,
        )
        for m in reversed(messages)
    ]
