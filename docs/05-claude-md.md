# SOFIE — Claude Code Instructions
**Read this file first before doing anything.**

---

## What Is SOFIE

SOFIE (Smart Output Factory for Image Execution) is a self-hosted AI creative account manager chatbot for social media agencies. It generates brand-compliant social media images through conversational interaction.

**Owner:** Code&Canvas Pte Ltd
**Pilot client:** Qurious Media
**Builder:** You (Claude Code), directed by Sukaimi

---

## Documentation

Read these before writing any code:

1. `docs/01-project-plan.md` — Phases, milestones, process
2. `docs/02-prd.md` — Product requirements, user flows, pipeline logic
3. `docs/03-tdd.md` — Architecture, services, APIs, data models, deployment
4. `docs/04-design-brief.md` — UI/UX specs for STITCH + UIUX Pro Max

---

## Critical Rules

### Design
- **ALWAYS** use STITCH (Google Design MCP) for layout and mockup generation before building UI
- **ALWAYS** use UIUX Pro Max skill for colour palette, typography, and UX guidelines
- **NEVER** freestyle colours or layouts. Generate via design tools first, then implement.
- Frontend: React + Tailwind CSS. Single-file components where possible.

### Architecture
- Backend: Python 3.12 + FastAPI
- LLM: Ollama (OpenAI-compatible API at localhost:11434)
- Image gen: ComfyUI API (localhost:8188)
- Brand memory: ChromaDB (localhost:8000)
- Data store: SQLite via SQLAlchemy
- All services communicate via localhost within Docker Compose

### Code Style
- Python: black formatter, isort, type hints everywhere
- React: functional components with hooks, no class components
- File naming: snake_case for Python, PascalCase for React components
- Comments: explain WHY, not WHAT
- Tests: pytest for backend, colocated with source where practical

### Pipeline
- Text in images is ALWAYS rendered via Pillow, NEVER by the image generation model
- Brand compliance checker uses LLM vision mode, not heuristics
- Max 3 regeneration attempts before escalating to human
- All image generation prompts must NOT contain text rendering instructions

### Deployment
- Everything runs in Docker Compose
- Models (Ollama, ComfyUI) stored in Docker volumes, not baked into images
- Brand assets mounted as volumes, not copied into containers
- `.env` for all secrets, gitignored
- `output/` directory gitignored

### What NOT To Do
- Do not use external paid APIs for core functionality (no OpenAI, no Anthropic API, no Replicate)
- Do not add authentication to the chat UI in POC (URL-only access)
- Do not build batch processing in POC
- Do not build video generation
- Do not build client login portal in POC
- Do not over-engineer: working > perfect

---

## Build Order

Follow this sequence:

1. **Docker Compose** — get Ollama + ComfyUI + ChromaDB running
2. **Backend skeleton** — FastAPI app, SQLite models, health check endpoints
3. **Pipeline steps** — brief parser → brand memory → prompt engineer → image gen → compositor → compliance checker (test each individually via CLI)
4. **Pipeline orchestrator** — wire steps together, test E2E via CLI
5. **Chat WebSocket** — real-time conversation with Sofie persona
6. **Frontend chat UI** — call STITCH + UIUX Pro Max FIRST, then implement
7. **Approval dashboard** — simple admin view
8. **Integration testing** — 10 consecutive E2E runs
9. **Dockerise app** — Dockerfile for SOFIE app container
10. **Deploy docs** — update README with deployment instructions

---

## Folder Structure

See `docs/03-tdd.md` §5 for the full directory tree. Follow it exactly.

---

## Environment Variables

```
OLLAMA_BASE_URL=http://ollama:11434
COMFYUI_BASE_URL=http://comfyui:8188
CHROMA_HOST=chromadb
CHROMA_PORT=8000
DATABASE_URL=sqlite:///data/sofie.db
GOOGLE_AI_STUDIO_KEY=  # optional, for fallback only
```

---

## When In Doubt

- Check the PRD (`docs/02-prd.md`)
- Check the TDD (`docs/03-tdd.md`)
- If neither answers the question, ask Sukaimi
- Prefer simple and working over clever and fragile
