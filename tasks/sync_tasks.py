from __future__ import annotations

import asyncio
import uuid

from core.sync_engine import SynchronizationEngine
from database.session import async_session_factory
from tasks.celery_app import celery_app


async def _run(job_id: str) -> dict[str, str | int]:
    async with async_session_factory() as session:
        job = await SynchronizationEngine(session).run(uuid.UUID(job_id))
        return {"job_id": str(job.id), "status": job.status.value, "conflict_count": job.conflict_count}


@celery_app.task(name="biometrics.sync_device", autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def sync_device(job_id: str) -> dict[str, str | int]:
    return asyncio.run(_run(job_id))
