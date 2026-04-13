# TDD.md — Technical Design Document
**SOFIE: Studio Orchestrator For Intelligent Execution**
**Version:** 1.0 (POC)
**Owner:** Code&Canvas Pte Ltd
**Last Updated:** 2026-04-13

---

## 1. Infrastructure

| Item | Spec |
|---|---|
| VPS | Hostinger KVM 2 |
| vCPU | 2 cores (AMD EPYC) |
| RAM | 8GB |
| Storage | 100GB NVMe SSD |
| Bandwidth | 8TB/month |
| OS | Ubuntu 24.04 LTS |
| Network | 1Gbps port |
| Containerisation | Docker + Docker Compose |

**RAM allocation (peak, 1 concurrent job):**

| Service | Est. RAM |
|---|---|
| FastAPI backend | 200MB |
| React (served static) | 50MB |
| Redis | 100MB |
| Celery worker | 200MB |
| Pillow compositor | 400MB |
| Cairo + Pango | 150MB |
| SQLite | 50MB |
| Streamlit dashboard | 150MB |
| Docker overhead | 300MB |
| **Total** | **~1.6GB** |
| **Headroom** | **~6.4GB** |

Processing is sequential. Multiple concurrent jobs not supported in POC.

---

## 2. Folder Structure

```
/sofie
  /backend
    __init__.py
    main.py                    # FastAPI app entry point
    config.py                  # Settings, env vars
    models.py                  # SQLAlchemy models
    schemas.py                 # Pydantic schemas
    /agents
      __init__.py
      sofie.py                 # Agent 1: Account Manager
      marcus.py                # Agent 2: Traffic Manager
      priya.py                 # Agent 3: Strategic Brief Analyst
      ray.py                   # Agent 4: Asset Manager
      celeste.py               # Agent 5: Art Director
      kai.py                   # Agent 5b: Compositor
      dana.py                  # Agent 6: QA Inspector
    /pipeline
      __init__.py
      orchestrator.py          # Wires all agents together
      brief_parser.py          # .docx extraction
      cost_tracker.py          # Per-job token + cost tracking
    /utils
      __init__.py
      llm_client.py            # Anthropic API wrapper
      image_gen_client.py      # Flux API wrapper (Replicate)
      asset_fetcher.py         # httpx link fetcher + validator
      compositor.py            # Pillow compositing functions
      text_renderer.py         # Cairo + Pango text functions
      file_server.py           # Download link generation
    /chat
      __init__.py
      websocket.py             # WebSocket handler
      sofie_persona.py         # Sofie system prompt + conversation logic
      memory.py                # In-conversation context
  /frontend
    /src
      App.jsx
      /components
        ChatWindow.jsx
        MessageBubble.jsx
        FileUpload.jsx
        ImagePreview.jsx
        TypingIndicator.jsx
        FeedbackMenu.jsx
      /hooks
        useWebSocket.js
      index.css
      main.jsx
    index.html
    package.json
    vite.config.js
  /dashboard
    operator.py                # Streamlit operator dashboard
  /brands
    /example-brand
      brand.md
      positioning.md
  /briefs
    brief-template.docx        # Downloadable template
  /output
    /job-id
      raw.png                  # Flux generated (if used)
      composited.jpg           # After Kai
      final.jpg                # After operator approval
      metadata.json            # Full job log
  /docs
    CLAUDE.md
    PRD.md
    TDD.md
    AGENTS.md
    FLOWS.md
    ENV.md
  /tests
    __init__.py
    test_brief_parser.py
    test_asset_fetcher.py
    test_compositor.py
    test_qa.py
    test_e2e.py
  docker-compose.yml
  docker-compose.dev.yml
  Dockerfile
  pyproject.toml
  .env.example
  .gitignore
  README.md
```

---

## 3. Data Models

### Job
```python
class Job(Base):
    __tablename__ = "jobs"

    id: str                    # JOB-{uuid12}
    created_at: datetime
    updated_at: datetime
    brand_name: str
    job_title: str
    conversation_id: str
    status: str                # pending | validating | compositing |
                               # qa | review | operator_review |
                               # approved | delivered | failed | escalated
    brief_json: dict           # Extracted brief fields
    asset_manifest: dict       # Validated assets + paths
    composition_plan: dict     # Celeste's layout instructions
    output_sizes: list[str]    # e.g. ["1080x1080", "1080x1350"]
    primary_size: str
    output_paths: dict         # size → file path
    qa_results: dict           # Dana's 3-check results
    compliance_attempts: int   # QA loop count
    user_revision_count: int   # User feedback loop count
    operator_notes: str        # Operator rejection notes
    total_tokens: int          # Running token count
    total_cost_usd: float      # Running cost
    cost_ceiling_usd: float    # Default 2.00
    cost_breached: bool
    error_log: str
```

### AgentLog
```python
class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: int
    job_id: str
    agent_name: str            # sofie | marcus | priya | ray | celeste | kai | dana
    step: str                  # brief_parse | asset_validate | compose | qa | etc.
    status: str                # started | completed | failed
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    notes: str
    created_at: datetime
```

### Conversation
```python
class Conversation(Base):
    __tablename__ = "conversations"

    id: str                    # CONV-{uuid12}
    created_at: datetime
    job_id: str                # nullable until job created
    messages: list[dict]       # [{role, content, timestamp}]
    state: str                 # greeting | awaiting_brief | validating |
                               # awaiting_feedback | revision | delivered
```

---

## 4. API Endpoints

### WebSocket
```
WS /ws/{conversation_id}
```
Handles all real-time chat between brand client and Sofie.

### REST
```
GET  /health                   # Health check
GET  /brief-template           # Download .docx template
POST /upload-brief             # Upload .docx brief
GET  /job/{job_id}/status      # Job status polling
GET  /job/{job_id}/download    # Download output files
GET  /operator/jobs            # List pending operator jobs
POST /operator/jobs/{job_id}/approve
POST /operator/jobs/{job_id}/reject
POST /operator/jobs/{job_id}/extend-budget
```

---

## 5. Agent Architecture

Each agent is a Python class with a standard interface:

```python
class BaseAgent:
    name: str
    model: str
    system_prompt: str

    async def run(
        self,
        job: Job,
        input_data: dict,
        on_status: callable | None = None
    ) -> dict:
        """
        Execute agent task.
        Returns output dict.
        Raises AgentError on failure.
        Logs to AgentLog.
        Updates job cost tracker.
        """
```

All agents log their token usage to AgentLog after every call.

---

## 6. Pipeline Orchestrator

```python
async def run_pipeline(job_id: str, on_status: callable) -> Job:

    # 1. Marcus: create job, assign ID
    await marcus.run(job, {})

    # 2. Priya: validate brief
    validation = await priya.run(job, {brief_text})
    if validation["has_blockers"]:
        await sofie.report_blockers(validation["blockers"])
        return job

    # 3. Font check
    font_issues = await check_fonts(job)
    if font_issues:
        await sofie.report_font_issues(font_issues)
        await wait_for_user_acknowledgement()

    # 4. Ray: fetch and validate assets
    assets = await ray.run(job, {links from brief})
    if assets["has_blockers"]:
        await sofie.report_asset_issues(assets["blockers"])
        return job

    # 5. Celeste: art direction + layout plan
    plan = await celeste.run(job, {assets, brief, references})

    # QA loop (max 3 attempts)
    for attempt in range(1, 4):

        # 6. Kai: composite image
        output = await kai.run(job, {plan, assets})

        # 7. Dana: QA check
        qa = await dana.run(job, {output, brief, plan})

        if qa["overall_pass"]:
            break
        elif attempt == 3:
            await escalate_to_operator(job, "qa_failed")
            return job
        else:
            plan = await celeste.revise_plan(qa["issues"])

    # Send to user for review
    await sofie.present_output(output)
```

---

## 7. LLM Client

```python
class LLMClient:
    """Wrapper for Anthropic API with cost tracking."""

    MODELS = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5-20251001"
    }

    COST_PER_MTK = {
        "claude-opus-4-6":          {"input": 15.00, "output": 75.00},
        "claude-sonnet-4-6":        {"input": 3.00,  "output": 15.00},
        "claude-haiku-4-5-20251001":{"input": 0.80,  "output": 4.00},
    }

    async def complete(
        self,
        model: str,
        messages: list[dict],
        system: str,
        max_tokens: int = 2048,
        images: list[bytes] | None = None,
        job_id: str | None = None,
        agent_name: str | None = None,
    ) -> tuple[str, int, int, float]:
        """
        Returns: (response_text, input_tokens, output_tokens, cost_usd)
        Logs to AgentLog if job_id provided.
        Checks cost ceiling before calling.
        """
```

---

## 8. Brief Parser

```python
async def parse_brief(docx_path: Path) -> dict:
    """
    Extract text from .docx using python-docx.
    Returns structured dict matching brief sections.
    Flags if content found in text boxes (unreadable).
    Returns extraction preview for user confirmation.
    """
```

**Extraction preview flow:**
1. Parse .docx
2. Return extracted fields to Sofie
3. Sofie presents summary to user: "Here's what I found in your brief. Is this correct?"
4. User confirms or corrects
5. Only then proceed to validation

---

## 9. Asset Fetcher

```python
async def fetch_asset(url: str, expected_type: str) -> AssetResult:
    """
    1. Check URL accessibility (HEAD request, timeout 10s)
    2. Download file (timeout 30s, max 50MB)
    3. Identify file type by content, not filename
    4. Run vision check if image
    5. Return AssetResult with path, type, issues
    """

class AssetResult:
    url: str
    local_path: Path | None
    identified_type: str       # logo | hero | element | font | reference | unknown
    format: str                # svg | png | jpg | otf | ttf
    dimensions: tuple | None
    has_transparency: bool | None
    usable: bool
    issues: list[str]
    classification: str        # BLOCKER | WARNING | OK
    advice: str | None         # User-facing fix advice
```

**Platform-specific error messages:**

| Platform | Error | Message to User |
|---|---|---|
| Google Drive | 403 | "This Google Drive link is restricted. Please change sharing to 'Anyone with the link can view'" |
| Dropbox | 404 | "This Dropbox link has expired. Please generate a new shared link" |
| WeTransfer | 410 | "This WeTransfer link has expired. Please re-upload and share a new link" |
| Any | Timeout | "This link timed out. Please check it is publicly accessible and try again" |

---

## 10. Compositor (Pillow)

```python
async def composite(
    plan: CompositionPlan,
    assets: AssetManifest,
    output_path: Path,
    dimensions: tuple[int, int],
) -> Path:
    """
    Layer order (bottom to top):
    1. Background
    2. Colour overlay
    3. Brand pattern/texture
    4. Hero image (resized + positioned)
    5. Design elements
    6. Logo (resized + positioned)
    7. Text layers (via Cairo)
    8. Mandatory text (via Cairo)

    Returns path to composited image.
    """
```

---

## 11. Text Renderer (Cairo + Pango)

```python
async def render_text_layer(
    base_image: Image,
    text_elements: list[TextElement],
    font_path: Path,
) -> Image:
    """
    Uses pycairo + pangocairo for proper typesetting.
    Handles: kerning, ligatures, line-height, text wrap,
    colour, size, weight, alignment.
    Returns composited image with text applied.
    """

class TextElement:
    content: str
    role: str          # headline | subcopy | cta | mandatory
    font_path: Path
    font_size: int
    font_weight: str   # regular | medium | bold
    colour: str        # hex
    position: tuple    # (x, y) as proportions 0.0-1.0
    max_width: int     # pixels
    alignment: str     # left | centre | right
```

**System dependencies (must be in Dockerfile):**
```dockerfile
RUN apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    pkg-config
```

---

## 12. Image Generation Client (Fallback Only)

Triggered only when no hero image is provided by client.

```python
async def generate_image(
    prompt: str,
    dimensions: tuple[int, int],
    reference_images: list[Path] | None,
    job_id: str,
) -> Path:
    """
    Uses Flux.1 Dev via Replicate API.
    Reference images used for style guidance.
    Prompt must NOT contain text rendering instructions.
    Returns path to generated image.
    """
```

**Prompt rules for Flux:**
- Include visual style, mood, colours, lighting, composition
- Include subject matter
- Never include text, words, typography instructions
- Never include logo placement instructions
- All text applied post-generation by Cairo

---

## 13. Cost Tracker

```python
class CostTracker:
    """Per-job token and cost accumulation."""

    async def record(
        self,
        job_id: str,
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate cost, add to job total.
        If total exceeds ceiling: raise CostCeilingBreached.
        Returns current total cost.
        """

    async def get_summary(self, job_id: str) -> dict:
        """Return per-agent breakdown and total."""
```

---

## 14. WebSocket Message Protocol

All messages follow this structure:

```json
{
  "type": "message | status | image | error | action_required",
  "role": "sofie | user | system",
  "content": "...",
  "job_id": "JOB-xxx",
  "metadata": {}
}
```

**Status types:**
```
parsing_brief | validating_assets | font_check | art_direction |
compositing | qa_check | awaiting_feedback | revision |
operator_review | delivered | failed | escalated | cost_ceiling_breached
```

---

## 15. Docker Compose

```yaml
services:

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  backend:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./brands:/app/brands:ro
      - ./briefs:/app/briefs:ro
      - output_data:/app/output
      - sqlite_data:/app/data
    depends_on:
      - redis
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    restart: unless-stopped

  celery:
    build: .
    command: celery -A backend.queue worker --loglevel=info --concurrency=1
    env_file: .env
    volumes:
      - ./brands:/app/brands:ro
      - output_data:/app/output
      - sqlite_data:/app/data
    depends_on:
      - redis
    restart: unless-stopped

  dashboard:
    build: .
    command: streamlit run dashboard/operator.py --server.port 8501
    env_file: .env
    ports:
      - "8501:8501"
    volumes:
      - sqlite_data:/app/data
      - output_data:/app/output
    restart: unless-stopped

volumes:
  redis_data:
  output_data:
  sqlite_data:
```

---

## 16. Dockerfile

```dockerfile
FROM python:3.12-slim

# System dependencies for Cairo + Pango
RUN apt-get update && apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    pkg-config \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 17. Python Dependencies

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "websockets>=13",
    "python-multipart>=0.0.9",
    "python-docx>=1.1",
    "httpx>=0.27",
    "anthropic>=0.40",
    "replicate>=0.34",
    "Pillow>=11.0",
    "pycairo>=1.27",
    "pangocairo>=0.3",
    "SQLAlchemy>=2.0",
    "aiosqlite>=0.20",
    "celery[redis]>=5.4",
    "streamlit>=1.40",
    "python-dotenv>=1.0",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
]
```

---

## 18. Upgrade Paths (Not POC)

| Component | POC | v1 Upgrade |
|---|---|---|
| Database | SQLite | PostgreSQL |
| Brand memory | File-based brand.md | ChromaDB RAG |
| Delivery | Download link | Google Drive API |
| Processing | Sequential | Parallel with job queue |
| Agents | 6 core | 12 full roster |
| Deployment | Hostinger KVM 2 | Hostinger KVM 4 or Railway |
| Auth | None | JWT per agency |
| Text render | Cairo + Pango | Cairo + Pango (same, already correct) |

---

## 19. Security Notes (POC)

- All secrets via .env — gitignored
- No authentication — URL-only access
- Input sanitisation on all user content
- File upload size limit: 50MB
- Accepted upload MIME types: .docx only
- Downloaded asset size limit: 50MB per file
- Output directory is not publicly browsable — file-specific links only
