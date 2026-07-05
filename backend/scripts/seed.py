"""
Seed MemoryMesh using the same ingestion pipeline as manual transcript upload.

For each sample meeting:
  1. meeting_service.create_meeting()  — status pending
  2. meeting_service.process_meeting() — LLM extraction, Cognee Remember/Improve, indexed

Run from repo root:
    python -m backend.scripts.seed
    pnpm --filter @workspace/scripts run seed
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select, text

from backend.database.connection import AsyncSessionLocal, TenantModel, init_db
from backend.models.memory import ForgetScope
from backend.scripts.seed_data import SAMPLE_MEETINGS
from backend.services.cognee_service import cognee_service
from backend.services.meeting_service import meeting_service
from backend.utils.logger import logger

TRUNCATE_SQL = text(
    """
    TRUNCATE TABLE chat_messages, activity_log, tasks, decision_history, decisions,
    entity_relationships, meeting_entities, projects, entities, meetings
    RESTART IDENTITY CASCADE
    """
)


async def _process_meeting_background(meeting_id: int) -> None:
    """Mirrors backend.api.routers.meetings._process_meeting_background."""
    async with AsyncSessionLocal() as db:
        try:
            await meeting_service.process_meeting(db, meeting_id)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("Background processing failed for meeting %d: %s", meeting_id, exc)
            raise


async def seed_for_tenant(tenant_id: int) -> None:
    print(f"\nSeeding tenant {tenant_id} via ingestion pipeline...")

    for sample in SAMPLE_MEETINGS:
        async with AsyncSessionLocal() as db:
            meeting = await meeting_service.create_meeting(
                db,
                {
                    "title": sample["title"],
                    "date": sample["date"],
                    "content": sample["content"],
                    "content_type": sample["content_type"],
                    "duration_minutes": sample.get("duration_minutes"),
                    "tags": sample.get("tags", []),
                },
                tenant_id=tenant_id,
            )
            await db.commit()
            meeting_id = meeting.id

        print(f"  Created meeting {meeting_id}: {sample['title']} — processing...")
        await _process_meeting_background(meeting_id)
        print(f"  Meeting {meeting_id} indexed.")

    print(f"  Tenant {tenant_id}: {len(SAMPLE_MEETINGS)} meetings processed.")


async def main() -> None:
    print("Seeding MemoryMesh (manual-upload pipeline: extract → Cognee Remember → Improve)...")

    await init_db()
    await cognee_service.initialize()

    if cognee_service.is_active:
        result = await cognee_service.forget(scope=ForgetScope.WORKSPACE)
        if result.success:
            print("Cleared existing Cognee workspace memory.")
        else:
            print(f"Warning: could not clear Cognee workspace: {result.message}")
    else:
        print("Cognee unavailable — meetings will be processed in SQL-only degraded mode.")

    async with AsyncSessionLocal() as db:
        await db.execute(TRUNCATE_SQL)
        await db.commit()
        print("Truncated meeting-derived SQL tables.")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TenantModel).order_by(TenantModel.id))
        tenants = result.scalars().all()

    if not tenants:
        print("No tenants found. Register/login at least once, then re-run seed.", file=sys.stderr)
        sys.exit(1)

    for tenant in tenants:
        await seed_for_tenant(tenant.id)

    print("\nSeed complete for all tenants.")
    print("Historical meetings span Nov 2025 – Jan 2026 (JWT → OAuth decision evolution).")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSeed interrupted.")
        sys.exit(130)
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
