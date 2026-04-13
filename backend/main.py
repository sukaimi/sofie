"""FastAPI application entry point for SOFIE.

Initialises the database, mounts routes, and configures CORS.
All configuration flows through config.settings — no direct env reads here.
"""

import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.models import Base, Job
from backend.schemas import HealthResponse, JobStatusResponse

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create database tables on startup, dispose engine on shutdown.

    Using lifespan instead of on_event because FastAPI deprecated the
    event-based approach in favour of the ASGI lifespan protocol.
    """
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title="SOFIE",
    description="Studio Orchestrator For Intelligent Execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for database sessions."""
    async with async_session() as session:
        yield session


# ── Health ────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Smoke test for load balancers and Docker health checks."""
    return HealthResponse()


# ── Brief template ────────────────────────────────────────────────────

@app.get("/brief-template", response_model=None)
async def download_brief_template() -> FileResponse | JSONResponse:
    """Serve the .docx brief template for brand clients."""
    if not settings.brief_template_path.exists():
        return JSONResponse(status_code=404, content={"error": "Brief template not found"})
    return FileResponse(
        path=settings.brief_template_path,
        filename="SOFIE-Brief-Template.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ── Brief upload ──────────────────────────────────────────────────────

@app.post("/upload-brief")
async def upload_brief(file: UploadFile) -> JSONResponse:
    """Accept a .docx brief upload and save to temp directory.

    Returns the temp file path so the WebSocket handler can trigger
    pipeline processing. File size is enforced by the upload limit.
    """
    if not file.filename or not file.filename.endswith(".docx"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only .docx files are accepted"},
        )

    # Save to temp with unique name to avoid collisions
    temp_path = settings.temp_dir / f"{uuid.uuid4().hex[:12]}_{file.filename}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return JSONResponse(
        content={"file_path": str(temp_path), "filename": file.filename}
    )


# ── Job status ────────────────────────────────────────────────────────

@app.get("/job/{job_id}/status", response_model=None)
async def get_job_status(
    job_id: str, session: AsyncSession = Depends(get_session)
) -> JobStatusResponse | JSONResponse:
    """Poll job status — used as fallback when WebSocket disconnects."""
    job = await session.get(Job, job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        brand_name=job.brand_name,
        job_title=job.job_title,
        total_cost_usd=job.total_cost_usd,
        compliance_attempts=job.compliance_attempts,
        user_revision_count=job.user_revision_count,
    )


# ── File download ─────────────────────────────────────────────────────

@app.get("/job/{job_id}/download/{filename}", response_model=None)
async def download_file(job_id: str, filename: str) -> FileResponse | JSONResponse:
    """Serve a specific output file for download.

    Validates the path exists and is within the output directory
    to prevent directory traversal attacks.
    """
    file_path = settings.output_dir / job_id / filename

    # Prevent path traversal
    if not file_path.resolve().is_relative_to(settings.output_dir.resolve()):
        return JSONResponse(status_code=403, content={"error": "Forbidden"})

    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "File not found"})

    return FileResponse(path=file_path, filename=filename)


# ── Operator endpoints ────────────────────────────────────────────────

@app.get("/operator/jobs")
async def list_operator_jobs(
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """List jobs pending operator review."""
    from sqlalchemy import select

    stmt = select(Job).where(
        Job.status.in_(["operator_review", "review", "escalated"])
    )
    result = await session.execute(stmt)
    jobs = result.scalars().all()

    return JSONResponse(
        content=[
            {
                "job_id": j.id,
                "brand_name": j.brand_name,
                "job_title": j.job_title,
                "status": j.status,
                "total_cost_usd": j.total_cost_usd,
                "qa_results": j.qa_results,
                "output_paths": j.output_paths,
                "created_at": j.created_at.isoformat() if j.created_at else "",
            }
            for j in jobs
        ]
    )


@app.post("/operator/jobs/{job_id}/approve")
async def approve_job(
    job_id: str, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    """Operator approves a job — triggers delivery."""
    job = await session.get(Job, job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    job.status = "approved"
    await session.commit()

    return JSONResponse(content={"job_id": job_id, "status": "approved"})


@app.post("/operator/jobs/{job_id}/reject")
async def reject_job(
    job_id: str, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    """Operator rejects a job with notes for revision."""
    job = await session.get(Job, job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    # Notes come from request body — handled by Sofie
    job.status = "compositing"
    await session.commit()

    return JSONResponse(content={"job_id": job_id, "status": "compositing"})


@app.post("/operator/jobs/{job_id}/extend-budget")
async def extend_budget(
    job_id: str, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    """Operator extends the cost ceiling for a job."""
    job = await session.get(Job, job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    job.cost_ceiling_usd += 1.00
    job.cost_breached = False
    job.status = "compositing"
    await session.commit()

    return JSONResponse(
        content={
            "job_id": job_id,
            "new_ceiling": job.cost_ceiling_usd,
            "status": "compositing",
        }
    )


# ── WebSocket ─────────────────────────────────────────────────────────

@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
) -> None:
    """WebSocket entry point — delegates to the chat handler."""
    from backend.chat.websocket import handle_websocket

    async with async_session() as session:
        await handle_websocket(websocket, conversation_id, session)
        await session.commit()
