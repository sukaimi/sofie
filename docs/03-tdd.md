# SOFIE — Technical Design Document
**Smart Output Factory for Image Execution**
**Version:** 1.0
**Owner:** Code&Canvas Pte Ltd
**Last Updated:** 2026-04-04

---

## 1. System Overview

SOFIE is a multi-service application running as a Docker Compose stack. All services communicate via localhost. No external API dependencies for core functionality (LLM and image gen are self-hosted).

```
┌─────────────────────────────────────────────────┐
│                   SOFIE STACK                    │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  SOFIE   │  │  OLLAMA  │  │   COMFYUI    │  │
│  │   APP    │──│  (LLM)   │  │  (IMAGE GEN) │  │
│  │  :3000   │  │  :11434  │  │    :8188     │  │
│  └────┬─────┘  └──────────┘  └──────────────┘  │
│       │                                          │
│  ┌────┴─────┐  ┌──────────┐                     │
│  │ CHROMADB │  │  SQLITE  │                     │
│  │  (RAG)   │  │  (STORE) │                     │
│  │  :8000   │  │  (file)  │                     │
│  └──────────┘  └──────────┘                     │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## 2. Services

### 2.1 SOFIE App (Core)
- **Language:** Python 3.12
- **Framework:** FastAPI (backend) + React (frontend)
- **Port:** 3000
- **Responsibilities:**
  - Serve chat UI (React SPA)
  - WebSocket handler for real-time chat
  - Conversation management
  - Pipeline orchestration (brief parsing → prompt engineering → image gen → compositing → compliance check)
  - Approval queue API
  - Brand management (CRUD for brand assets)

### 2.2 Ollama (LLM Server)
- **Model:** Gemma 4 26B-A4B-it (MoE, 3.8B active params)
- **Fallback:** Qwen 3 8B-it or Gemma 3 12B-it (if Gemma 4 GGUF unavailable)
- **Port:** 11434
- **API:** OpenAI-compatible (`/v1/chat/completions`)
- **Used for:**
  - Conversation (Sofie persona)
  - Brief extraction (structured JSON output)
  - Prompt engineering (image gen prompt from brief + brand context)
  - Brand compliance checking (vision mode, image + brand guidelines → pass/fail)

### 2.3 ComfyUI (Image Generation Server)
- **Model:** Flux.1 Schnell (Apache 2.0, commercial use OK)
- **Format:** FP8 checkpoint (~12GB VRAM)
- **Port:** 8188
- **API:** ComfyUI REST API (queue prompt → poll for result → download image)
- **Used for:** All image generation requests
- **VRAM budget:** ~12GB for Flux Schnell FP8

### 2.4 ChromaDB (Brand Memory)
- **Port:** 8000
- **Used for:** Vector search over brand documents
- **Collections:** One per brand
- **Ingestion:** On brand creation, all .md files chunked and embedded
- **Embedding model:** Ollama's built-in embedding (nomic-embed-text or similar)

### 2.5 SQLite (Data Store)
- **File:** `/data/sofie.db`
- **Tables:**

```sql
-- Conversations
CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  brand_id TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Messages
CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT REFERENCES conversations(id),
  role TEXT CHECK(role IN ('user', 'assistant', 'system')),
  content TEXT,
  metadata JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Jobs (image generation requests)
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  conversation_id TEXT REFERENCES conversations(id),
  brand_id TEXT,
  brief_json JSON,
  image_prompt TEXT,
  status TEXT CHECK(status IN ('pending', 'generating', 'compositing', 'checking', 'review', 'approved', 'rejected', 'failed')),
  attempts INTEGER DEFAULT 0,
  output_path TEXT,
  compliance_score REAL,
  compliance_notes TEXT,
  operator_notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Brands
CREATE TABLE brands (
  id TEXT PRIMARY KEY,
  name TEXT,
  summary_path TEXT,
  assets_path TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Pipeline Detail

### Step 1: Conversation → Brief Extraction
- **Input:** Last N messages from conversation
- **LLM call:** System prompt instructs Gemma 4 to extract structured brief JSON from natural conversation
- **Output:** Validated JSON matching the brief schema (see [[02-prd]] §9)
- **Validation:** JSON schema check. If missing required fields, Sofie asks follow-up questions instead of generating.

### Step 2: Brand Context Retrieval
- **Input:** `brand_id` from brief
- **Action:** Query ChromaDB for relevant brand chunks (top 10 by similarity to brief content)
- **Output:** Concatenated brand context string (colour palette, typography, logo rules, tone, do's/don'ts)
- **Also loads:** Logo file path, font file path, brand element paths from filesystem

### Step 3: Prompt Engineering
- **Input:** Brief JSON + brand context
- **LLM call:** System prompt instructs Gemma 4 to generate a detailed image generation prompt
- **Constraints:**
  - Must NOT include text rendering instructions (text handled by compositor)
  - Must reference brand colour palette
  - Must describe composition, mood, subject, lighting
  - Must specify aspect ratio matching brief dimensions
- **Output:** `image_gen_prompt` string stored in job record

### Step 4: Image Generation
- **Input:** `image_gen_prompt`
- **Action:** POST to ComfyUI API with Flux.1 Schnell workflow
- **Workflow:** Text-to-image, configured for brief dimensions, 4 inference steps (Schnell is optimised for this)
- **Output:** Raw generated image saved to `/output/{job_id}/raw.png`
- **Timeout:** 60 seconds. If exceeded, retry once, then fail.

### Step 5: Compositing
- **Input:** Raw image + brand assets (logo, fonts, text overlays from brief)
- **Action:** Pillow/PIL script:
  1. Load raw image
  2. Apply text overlays at specified positions using brand font
  3. Place logo at specified position with safe zone padding
  4. Apply any brand elements (borders, frames, patterns)
  5. Export as final JPG/PNG at target dimensions
- **Output:** `/output/{job_id}/final.png`

### Step 6: Brand Compliance Check
- **Input:** Final composited image + brand summary text
- **LLM call:** Gemma 4 vision mode. System prompt: "You are a brand compliance reviewer. Compare this image against the brand guidelines provided. Score 1-10 and list any violations."
- **Output:** Score (1-10) + notes
- **Logic:**
  - Score ≥ 7: Pass → move to approval queue
  - Score 4-6: Auto-retry (back to Step 3 with compliance notes as additional context)
  - Score < 4: Fail → escalate to operator with notes
  - Max 3 attempts total

### Step 7: Approval Queue
- **Input:** Final image + job metadata
- **Action:** Job status set to `review`. Appears in approval dashboard.
- **Operator actions:** Approve (→ status `approved`) or Reject with notes (→ status `rejected`, re-enters revision loop via chat)

### Step 8: Delivery
- **Input:** Approved image
- **Action:** Image URL sent back to chat conversation. Available for download.

---

## 4. API Endpoints

### Chat
| Method | Path | Description |
|---|---|---|
| GET | `/` | Serve React chat UI |
| WS | `/ws/chat/{conversation_id}` | WebSocket for real-time chat |
| POST | `/api/conversations` | Create new conversation |
| GET | `/api/conversations/{id}/messages` | Get message history |

### Approval Queue
| Method | Path | Description |
|---|---|---|
| GET | `/api/queue` | List pending approvals |
| GET | `/api/queue/{job_id}` | Get job detail + image |
| POST | `/api/queue/{job_id}/approve` | Approve job |
| POST | `/api/queue/{job_id}/reject` | Reject with notes |

### Brands
| Method | Path | Description |
|---|---|---|
| GET | `/api/brands` | List brands |
| POST | `/api/brands` | Create brand (upload assets) |
| GET | `/api/brands/{id}` | Get brand detail |

### Images
| Method | Path | Description |
|---|---|---|
| GET | `/api/images/{job_id}/final` | Download final image |
| GET | `/api/images/{job_id}/raw` | Download raw (pre-composite) image |

---

## 5. Directory Structure

```
sofie/
├── docker-compose.yml
├── Dockerfile
├── claude.md
├── README.md
├── .env.example
├── .gitignore
│
├── docs/                          # Obsidian vault
│   ├── 01-project-plan.md
│   ├── 02-prd.md
│   ├── 03-tdd.md
│   ├── 04-design-brief.md
│   └── 05-claude-md.md
│
├── backend/
│   ├── main.py                    # FastAPI entrypoint
│   ├── config.py                  # Environment + settings
│   ├── models.py                  # SQLite models (SQLAlchemy)
│   ├── schemas.py                 # Pydantic schemas
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── brief_parser.py        # Step 1: conversation → structured brief
│   │   ├── brand_memory.py        # Step 2: ChromaDB retrieval
│   │   ├── prompt_engineer.py     # Step 3: brief + brand → image prompt
│   │   ├── image_generator.py     # Step 4: ComfyUI API call
│   │   ├── compositor.py          # Step 5: Pillow text/logo overlay
│   │   ├── compliance_checker.py  # Step 6: vision LLM review
│   │   └── orchestrator.py        # Pipeline coordinator
│   │
│   ├── chat/
│   │   ├── __init__.py
│   │   ├── websocket.py           # WebSocket handler
│   │   ├── sofie_persona.py       # System prompt + persona logic
│   │   └── memory.py              # Conversation memory manager
│   │
│   ├── queue/
│   │   ├── __init__.py
│   │   └── approval.py            # Approval queue logic
│   │
│   └── utils/
│       ├── __init__.py
│       ├── llm_client.py          # Ollama API wrapper (OpenAI-compatible)
│       ├── comfyui_client.py      # ComfyUI API wrapper
│       └── fallback.py            # Circuit breaker + Google AI Studio fallback
│
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx
│   │   │   ├── MessageBubble.jsx
│   │   │   ├── ImagePreview.jsx
│   │   │   ├── TypingIndicator.jsx
│   │   │   └── ApprovalDashboard.jsx
│   │   ├── hooks/
│   │   │   └── useWebSocket.js
│   │   └── styles/
│   │       └── tailwind.css
│   └── public/
│       └── index.html
│
├── brands/                        # Brand assets (gitignored, mounted as volume)
│   └── example-brand/
│       ├── brand.md
│       ├── positioning.md
│       └── assets/
│           ├── logo.svg
│           ├── font.otf
│           ├── images/
│           ├── elements/
│           └── references/
│
├── comfyui/
│   └── workflows/
│       └── flux-schnell-txt2img.json   # Default ComfyUI workflow
│
├── output/                        # Generated images (gitignored)
│   └── {job_id}/
│       ├── raw.png
│       ├── final.png
│       └── metadata.json
│
└── tests/
    ├── test_brief_parser.py
    ├── test_prompt_engineer.py
    ├── test_compositor.py
    ├── test_compliance_checker.py
    └── test_pipeline_e2e.py
```

---

## 6. Docker Compose

```yaml
version: "3.8"

services:
  sofie:
    build: .
    ports:
      - "3000:3000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - COMFYUI_BASE_URL=http://comfyui:8188
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8000
      - DATABASE_URL=sqlite:///data/sofie.db
      - GOOGLE_AI_STUDIO_KEY=${GOOGLE_AI_STUDIO_KEY:-}
    volumes:
      - ./brands:/app/brands
      - ./output:/app/output
      - sofie-data:/data
    depends_on:
      - ollama
      - comfyui
      - chromadb

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  comfyui:
    image: yanwk/comfyui-boot:latest
    ports:
      - "8188:8188"
    volumes:
      - comfyui-models:/root/ComfyUI/models
      - ./comfyui/workflows:/root/ComfyUI/user/default/workflows
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma-data:/chroma/chroma

volumes:
  sofie-data:
  ollama-models:
  comfyui-models:
  chroma-data:
```

---

## 7. VRAM Budget (RTX 3090, 24GB)

| Component | VRAM | Notes |
|---|---|---|
| Gemma 4 26B MoE (Q4) | ~8-10 GB | Only 3.8B active params per forward pass |
| Flux.1 Schnell FP8 | ~12 GB | Loaded on-demand, unloaded after generation |
| **Total peak** | ~22 GB | Sequential loading: LLM active during chat, Flux loaded for image gen |

**Strategy:** Ollama keeps LLM loaded. When image gen is triggered, ComfyUI loads Flux (already cached in VRAM if space allows). If OOM, Ollama can temporarily offload layers to CPU. This is managed automatically by Ollama's memory management.

**Fallback GPU plan:** If 24GB is too tight, downgrade LLM to Qwen 2.5 7B (~5GB Q4) and keep Flux full-time. Loses some reasoning quality but gains VRAM headroom.

---

## 8. Deployment

### Local Development
```bash
# Clone
git clone git@github.com:codeandcanvas/sofie.git
cd sofie

# Copy env
cp .env.example .env

# Start stack
docker compose up -d

# Pull LLM model (first time only)
docker exec -it sofie-ollama-1 ollama pull gemma4:26b-a4b

# Download Flux.1 Schnell (first time only)
# Via ComfyUI Manager or manual download to comfyui-models volume

# Access
open http://localhost:3000
```

### Production (RunPod/Vast.ai)
```bash
# SSH into GPU instance
ssh root@<instance-ip>

# Clone repo
git clone git@github.com:codeandcanvas/sofie.git
cd sofie

# Copy env and configure
cp .env.example .env
nano .env  # set GOOGLE_AI_STUDIO_KEY for fallback

# Start
docker compose up -d

# Pull models (first time)
docker exec -it sofie-ollama-1 ollama pull gemma4:26b-a4b

# Expose via Cloudflare Tunnel (optional)
cloudflared tunnel --url http://localhost:3000
```

### Update Process
```bash
# On GPU instance
cd sofie
git pull origin main
docker compose build sofie  # rebuild app only
docker compose up -d sofie  # restart app, keep Ollama/ComfyUI running
```

### Future: GitHub Actions CI/CD
```yaml
# .github/workflows/deploy.yml (future)
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: SSH deploy
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.GPU_HOST }}
          username: root
          key: ${{ secrets.GPU_SSH_KEY }}
          script: |
            cd /root/sofie
            git pull origin main
            docker compose build sofie
            docker compose up -d sofie
```

---

## 9. Security (POC Level)

- No client auth in POC (URL-only access)
- Admin/approval dashboard behind basic HTTP auth
- All data stays on GPU instance (no external data transmission except optional Google AI Studio fallback)
- `.env` file gitignored, secrets not in repo
- Brand assets mounted as Docker volume, not baked into image

---

## 10. Testing Strategy

| Type | Tool | Coverage |
|---|---|---|
| Unit tests | pytest | Each pipeline step individually |
| Integration tests | pytest + httpx | API endpoints + pipeline E2E |
| Manual testing | Browser | Chat UX, approval flow, image quality |
| Load testing | locust (future) | Concurrent chat sessions |

### Key Test Cases
1. Brief extraction from conversational input produces valid JSON
2. Brand context retrieval returns relevant chunks (not random)
3. Image prompt does NOT contain text rendering instructions
4. Compositor correctly places logo at specified position
5. Compositor correctly renders text using brand font
6. Compliance checker rejects image with wrong colour palette
7. Revision loop regenerates on feedback (max 3 attempts)
8. Circuit breaker activates when Ollama is down
9. WebSocket maintains connection during long image generation
10. Approval flow transitions job status correctly

---

## 11. Cross-References

- [[01-project-plan]] — Project Plan
- [[02-prd]] — Product Requirements Document
- [[04-design-brief]] — UI/UX Design Brief
- [[05-claude-md]] — Claude Code Instruction File
