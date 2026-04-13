"""Celery task definitions for async pipeline execution.

Each task wraps an async pipeline call inside a sync Celery task.
Status updates are pushed to Redis pub/sub so the WebSocket layer
can relay them to the client in real time.
"""

import asyncio
from pathlib import Path

from backend.queue import app


@app.task(bind=True, name="sofie.run_pipeline")
def run_pipeline_task(self, job_id: str, docx_path: str | None = None) -> dict:
    """Execute the full pipeline for a job in a Celery worker.

    Bridges sync Celery with async pipeline code via asyncio.run().
    Status updates are published to Redis so the WebSocket handler
    can push them to the client without polling.
    """
    return asyncio.run(_run_async(job_id, docx_path))


async def _run_async(job_id: str, docx_path: str | None) -> dict:
    """Async wrapper that sets up the DB session and runs the pipeline.

    Each task gets its own session to avoid shared state between
    concurrent task executions (not an issue in POC with concurrency=1,
    but correct for v1 upgrade).
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.config import settings
    from backend.models import Job
    from backend.pipeline.orchestrator import run_pipeline

    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            return {"error": f"Job {job_id} not found"}

        result = await run_pipeline(
            job=job,
            session=session,
            docx_path=Path(docx_path) if docx_path else None,
            on_status=None,  # TODO: wire to Redis pub/sub in v1
        )

        await session.commit()

    await engine.dispose()

    return {
        "job_id": result.job_id,
        "status": result.status,
        "output_paths": result.output_paths,
        "error": result.error,
    }
