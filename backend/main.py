import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from sqlalchemy import func

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend.config import settings
from backend.models import (
    Brand,
    Conversation,
    Job,
    Message,
    async_session,
    init_db,
)
from backend.schemas import (
    BrandCreate,
    BrandOnboardSchema,
    BrandResponse,
    ConversationCreate,
    ConversationResponse,
    HealthResponse,
    JobRejectRequest,
    JobResponse,
    MessageResponse,
)
from backend.utils import comfyui_client, llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _preload_brands() -> None:
    """Pre-load existing brands into DB and ChromaDB on startup."""
    from backend.pipeline.brand_memory import ingest_brand

    if not settings.brands_dir.exists():
        return

    for brand_dir in settings.brands_dir.iterdir():
        if not brand_dir.is_dir() or not (brand_dir / "brand.md").exists():
            continue

        brand_id = brand_dir.name
        async with async_session() as session:
            existing = await session.get(Brand, brand_id)
            if not existing:
                # Read brand name from brand.md first line
                brand_md = (brand_dir / "brand.md").read_text()
                name = brand_id.replace("-", " ").title()
                for line in brand_md.split("\n"):
                    if line.startswith("## Brand Name"):
                        idx = brand_md.index(line) + len(line)
                        next_line = brand_md[idx:].strip().split("\n")[0].strip()
                        if next_line:
                            name = next_line
                        break

                brand = Brand(
                    id=brand_id,
                    name=name,
                    summary_path=str(brand_dir / "brand.md"),
                    assets_path=str(brand_dir / "assets"),
                )
                session.add(brand)
                await session.commit()
                logger.info(f"Pre-loaded brand: {name} ({brand_id})")

        # Ingest into ChromaDB
        try:
            count = await ingest_brand(brand_id, brand_dir)
            logger.info(f"Ingested {count} chunks for brand '{brand_id}'")
        except Exception as e:
            logger.warning(f"Failed to ingest brand '{brand_id}': {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info("Database initialized")

    ollama_ok = await llm_client.check_health()
    logger.info(f"Ollama: {'connected' if ollama_ok else 'NOT available'}")

    comfyui_ok = await comfyui_client.check_health()
    mock_label = " (mocked)" if settings.comfyui_mock else ""
    logger.info(f"ComfyUI: {'ready' if comfyui_ok else 'NOT available'}{mock_label}")

    # Pre-load example brand into DB and ChromaDB
    await _preload_brands()

    yield
    # Shutdown
    logger.info("Shutting down")


app = FastAPI(title="SOFIE", version="0.1.0", lifespan=lifespan)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- WebSocket Chat ---


@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(websocket: WebSocket, conversation_id: str):
    from backend.chat.websocket import chat_handler

    await chat_handler(websocket, conversation_id)


# --- Health ---


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    ollama_ok = await llm_client.check_health()
    comfyui_ok = await comfyui_client.check_health()

    return HealthResponse(
        ollama="ok" if ollama_ok else "unavailable",
        chromadb="ok",  # TODO: actual check
        comfyui=comfyui_client.get_image_gen_mode() if comfyui_ok else "unavailable",
        database="ok",
    )


# --- Conversations ---


@app.post("/api/conversations", response_model=ConversationResponse)
async def create_conversation(body: ConversationCreate):
    async with async_session() as session:
        conv = Conversation(brand_id=body.brand_id)
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return ConversationResponse(
            id=conv.id, brand_id=conv.brand_id, created_at=conv.created_at
        )


@app.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def get_messages(conversation_id: str):
    async with async_session() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return [
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ]


# --- Approval Queue ---


@app.get("/api/queue", response_model=list[JobResponse])
async def list_queue():
    async with async_session() as session:
        result = await session.execute(
            select(Job).where(Job.status == "review").order_by(Job.created_at.desc())
        )
        jobs = result.scalars().all()
        return [_job_to_response(j) for j in jobs]


@app.get("/api/queue/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return _job_to_response(job)


@app.post("/api/queue/{job_id}/approve", response_model=JobResponse)
async def approve_job(job_id: str):
    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.status != "review":
            raise HTTPException(400, f"Job is not in review (status: {job.status})")
        job.status = "approved"
        await session.commit()
        await session.refresh(job)
        return _job_to_response(job)


@app.post("/api/queue/{job_id}/reject", response_model=JobResponse)
async def reject_job(job_id: str, body: JobRejectRequest):
    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.status != "review":
            raise HTTPException(400, f"Job is not in review (status: {job.status})")
        job.status = "rejected"
        job.operator_notes = body.notes
        await session.commit()
        await session.refresh(job)
        return _job_to_response(job)


# --- Brands ---


@app.get("/api/brands", response_model=list[BrandResponse])
async def list_brands():
    async with async_session() as session:
        result = await session.execute(select(Brand).order_by(Brand.name))
        brands = result.scalars().all()
        return [_brand_to_response(b) for b in brands]


@app.post("/api/brands", response_model=BrandResponse)
async def create_brand(body: BrandCreate):
    async with async_session() as session:
        brand = Brand(
            name=body.name,
            summary_path=body.summary_path,
            assets_path=body.assets_path,
        )
        session.add(brand)
        await session.commit()
        await session.refresh(brand)
        return _brand_to_response(brand)


@app.get("/api/brands/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: str):
    async with async_session() as session:
        brand = await session.get(Brand, brand_id)
        if not brand:
            raise HTTPException(404, "Brand not found")
        return _brand_to_response(brand)


MAX_BRANDS = 3


@app.post("/api/brands/onboard", response_model=BrandResponse)
async def onboard_brand(body: BrandOnboardSchema):
    """Create a brand from conversational onboarding data."""
    from backend.pipeline.brand_memory import ingest_brand

    async with async_session() as session:
        # Enforce max brands
        count_result = await session.execute(select(func.count(Brand.id)))
        count = count_result.scalar()
        if count >= MAX_BRANDS:
            raise HTTPException(
                400,
                f"Maximum {MAX_BRANDS} brands allowed. Delete one before adding a new brand.",
            )

    # Generate brand_id from name
    brand_id = body.name.lower().replace(" ", "-").replace("'", "")

    # Create brand directory and brand.md
    brand_dir = settings.brands_dir / brand_id
    brand_dir.mkdir(parents=True, exist_ok=True)

    # Generate brand.md content
    colours_section = "\n".join(
        f"- **{c.get('name', 'Color')}:** {c.get('hex', '#000000')}"
        for c in body.colours
    ) if body.colours else "- Not specified"

    dos_section = "\n".join(f"- {d}" for d in body.dos) if body.dos else "- Not specified"
    donts_section = "\n".join(f"- {d}" for d in body.donts) if body.donts else "- Not specified"

    brand_md = f"""# {body.name} — Brand Guidelines

## Brand Name
{body.name}

## Tagline
{f'"{body.tagline}"' if body.tagline else 'Not specified'}

## Brand Summary
{body.summary}

## Colour Palette
{colours_section}

## Typography
{body.typography or 'Not specified'}

## Tone of Voice
{body.tone or 'Not specified'}

## Target Audience
{body.target_audience or 'Not specified'}

## Do's
{dos_section}

## Don'ts
{donts_section}
"""

    brand_md_path = brand_dir / "brand.md"
    brand_md_path.write_text(brand_md, encoding="utf-8")

    # Create assets directory
    (brand_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (brand_dir / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    (brand_dir / "assets" / "elements").mkdir(parents=True, exist_ok=True)

    # Ingest into ChromaDB
    await ingest_brand(brand_id, brand_dir)

    # Create DB record
    async with async_session() as session:
        brand = Brand(
            id=brand_id,
            name=body.name,
            summary_path=str(brand_md_path),
            assets_path=str(brand_dir / "assets"),
        )
        session.add(brand)
        await session.commit()
        await session.refresh(brand)
        return _brand_to_response(brand)


@app.delete("/api/brands/{brand_id}")
async def delete_brand(brand_id: str):
    """Delete a brand and all its data."""
    from backend.pipeline.brand_memory import _get_client as get_chroma_client

    async with async_session() as session:
        brand = await session.get(Brand, brand_id)
        if not brand:
            raise HTTPException(404, "Brand not found")
        await session.delete(brand)
        await session.commit()

    # Delete ChromaDB collection
    try:
        chroma = get_chroma_client()
        chroma.delete_collection(name=brand_id)
    except Exception:
        pass

    # Delete brand directory
    brand_dir = settings.brands_dir / brand_id
    if brand_dir.exists():
        shutil.rmtree(brand_dir)

    return {"deleted": brand_id}


# --- Images ---


@app.get("/api/images/{job_id}/final")
async def get_final_image(job_id: str):
    path = settings.output_dir / job_id / "final.png"
    if not path.exists():
        raise HTTPException(404, "Final image not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/images/{job_id}/raw")
async def get_raw_image(job_id: str):
    path = settings.output_dir / job_id / "raw.png"
    if not path.exists():
        raise HTTPException(404, "Raw image not found")
    return FileResponse(path, media_type="image/png")


# --- Helpers ---


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        conversation_id=job.conversation_id,
        brand_id=job.brand_id,
        status=job.status,
        attempts=job.attempts,
        compliance_score=job.compliance_score,
        compliance_notes=job.compliance_notes,
        operator_notes=job.operator_notes,
        output_path=job.output_path,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _brand_to_response(brand: Brand) -> BrandResponse:
    return BrandResponse(
        id=brand.id,
        name=brand.name,
        summary_path=brand.summary_path,
        assets_path=brand.assets_path,
        created_at=brand.created_at,
    )


# --- Serve frontend (production) ---
# Mount built React SPA as static files. Must be last to avoid overriding API routes.
frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dir.exists():
    from fastapi.responses import HTMLResponse

    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for any non-API route."""
        index = frontend_dir / "index.html"
        return HTMLResponse(index.read_text())
