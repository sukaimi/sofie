# CLAUDE.md — SOFIE Build Instructions
**Read this file first. Before touching any code.**

---

## What Is SOFIE

**SOFIE** = Studio Orchestrator For Intelligent Execution

SOFIE is an AI-powered creative composition engine with a conversational front-end. It is not an image generator. It is a brand-compliant static image compositor operated by a team of specialised AI agents, delivered through a chat interface powered by an AI account manager persona named Sofie.

**Owner:** Code&Canvas Pte Ltd
**Builder:** Claude Code
**Pilot client:** Agency (unnamed in codebase — keep agency-agnostic)
**Deployment:** Hostinger KVM 2 VPS, Docker Compose

---

## Critical First Instruction

**The previous SOFIE build is deprecated.**

Do the following before writing any new code:

1. Read all 6 documentation files in `/docs/`
2. Preserve from the old build:
   - WebSocket architecture pattern
   - Docker Compose skeleton
   - FastAPI app structure
   - `.env` loading pattern
3. Discard from the old build:
   - All ComfyUI references and clients
   - All Ollama references and clients
   - ChromaDB and all RAG infrastructure
   - Old pipeline step implementations
   - Old agent prompts and persona files
4. Start fresh implementations for everything else

---

## Documentation Files — Read All Before Coding

| File | Purpose |
|---|---|
| `docs/CLAUDE.md` | This file — master build instructions |
| `docs/PRD.md` | Product requirements, flows, rules |
| `docs/TDD.md` | Technical design, stack, folder structure, APIs |
| `docs/AGENTS.md` | All agents — names, models, prompts, I/O |
| `docs/FLOWS.md` | All user flows in detail |
| `docs/ENV.md` | All environment variables and API keys |

---

## Architecture in One Paragraph

A brand client uploads a `.docx` brief via a React chat UI. Sofie (Claude Sonnet) receives it conversationally. A pipeline of 6 AI agents processes the brief: validating it, checking assets, interpreting layout references, compositing layers using Pillow (images) and Cairo+Pango (text), running internal QA, and presenting output to the user. After 1-2 user revision rounds, an agency operator approves via a simple dashboard. The final image is delivered as a download link. All agent LLM calls use the Anthropic API. Image generation (Flux.1 Dev via Replicate) is a fallback only — triggered when no hero image is provided.

---

## POC Agent Roster (6 Core Agents)

| # | Name | Role | Model |
|---|---|---|---|
| 1 | Sofie | Account manager, chat interface | Claude Sonnet 4.6 |
| 2 | Marcus | Traffic manager, job state | Claude Haiku 4.5 |
| 3 | Priya | Strategic brief analyst | Claude Opus 4.6 |
| 4 | Ray | Asset manager, vision checks | Claude Sonnet 4.6 (vision) |
| 5 | Celeste + Kai | Art direction + composition | Claude Opus 4.6 (vision) + Pillow/Cairo |
| 6 | Dana | QA inspector | Claude Sonnet 4.6 (vision) |

Noel (human operator) uses the approval dashboard — no LLM.
Full 12-agent roster activates in v1.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Framework | FastAPI (async) |
| Frontend | React 18 + Tailwind CSS |
| Real-time | WebSocket |
| Brief parsing | python-docx |
| Asset fetching | httpx |
| Image compositing | Pillow (PIL) |
| Text rendering | Cairo + Pango (pycairo + pangocairo) |
| Image generation | Flux.1 Dev via Replicate API (fallback only) |
| LLM | Anthropic API (Claude Sonnet 4.6, Opus 4.6, Haiku 4.5) |
| Database | SQLite via SQLAlchemy (async, aiosqlite) |
| Job queue | Celery + Redis |
| Operator dashboard | Streamlit |
| Container | Docker + Docker Compose |
| Deployment | Hostinger KVM 2 VPS |
| OS | Ubuntu 24.04 LTS |

---

## Design Rules

### UI
- Simple and modern — no skeuomorphic elements, no heavy gradients
- React + Tailwind CSS only
- Single-file components where possible
- Chat UI is the only brand client interface
- Operator dashboard is Streamlit — functional, not beautiful
- No authentication in POC (URL-only access)

### Code
- Python: black formatter, isort, type hints everywhere
- React: functional components with hooks only, no class components
- File naming: snake_case Python, PascalCase React
- Comments: explain WHY not WHAT
- Every function must have a docstring

### Pipeline
- Text in images: ALWAYS Cairo + Pango, NEVER the image generation model
- Image compositing: ALWAYS Pillow
- All image generation prompts must NOT contain text rendering instructions
- Max 3 internal QA loops before escalating to operator
- Max 2 user revision rounds before escalating to operator
- Every agent writes output to job state (SQLite) before passing to next agent
- Failed jobs must be resumable from last successful step

### Cost
- Track token usage per agent per job
- Hard cost ceiling: $2.00 per job
- If ceiling breached: pause job, alert operator, do not continue

### Security
- All secrets via .env — never hardcoded
- No authentication for POC
- Input sanitisation on all user-submitted content

---

## Build Order

Follow this sequence strictly:

1. Docker Compose — Redis, SQLite volume setup
2. FastAPI skeleton — health check, .env loading, DB init
3. SQLite models — Job, AgentLog, CostTracker
4. Brief parser — .docx extraction + preview confirmation
5. Asset validator — link checker, vision identifier (Ray)
6. Brief validator — field checker, strategy check (Priya)
7. Art direction — layout analysis, composition plan (Celeste)
8. Compositor — Pillow layers + Cairo text (Kai)
9. QA checker — 3-check vision inspection (Dana)
10. Orchestrator — wire all steps, job state, retry logic
11. Celery job queue — async job processing
12. WebSocket chat — Sofie persona, real-time updates
13. React frontend — chat UI, file upload, image preview
14. Operator dashboard — Streamlit approval view
15. Cost tracker — per-agent token counting, ceiling enforcement
16. Docker build — Dockerfile for app container
17. Integration testing — 10 consecutive E2E runs
18. Deploy — push to Hostinger KVM 2

---

## What NOT To Do

- Do not use ComfyUI
- Do not use Ollama
- Do not use ChromaDB
- Do not build batch processing in POC
- Do not build video generation
- Do not build client login portal in POC
- Do not build Google Drive integration in POC (v1 feature)
- Do not add authentication to chat UI in POC
- Do not render text via image generation models
- Do not process multiple sizes in parallel (sequential only in POC)
- Do not over-engineer: working beats perfect

---

## When In Doubt

1. Check PRD.md for product decisions
2. Check TDD.md for technical decisions
3. Check AGENTS.md for agent behaviour
4. Check FLOWS.md for flow logic
5. If none of the above answers it — ask Sukaimi
