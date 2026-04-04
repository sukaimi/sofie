# SOFIE — Project Plan
**Smart Output Factory for Image Execution**
**Version:** 1.0
**Owner:** Code&Canvas Pte Ltd
**Client:** Qurious Media
**Last Updated:** 2026-04-04

---

## 1. What Is SOFIE

A self-hosted, white-label AI creative account manager chatbot that generates brand-compliant social media images for agency clients. Powered by open-source LLMs and image generation models. Zero API token costs.

**Core interaction:** Brand client opens chat → talks to "Sofie" (AI account manager) → describes what they need → Sofie generates copy + images → Qurious team approves → client receives final assets.

---

## 2. Process Framework

**Adapted Lean UX + Kanban** — suited for a POC with a solo builder (you + Claude Code) and fast iteration cycles.

### Why This Framework
- No sprints needed for a solo build — Kanban's continuous flow is faster
- Lean UX validates assumptions early (build → measure → learn)
- Obsidian vault as the single source of truth keeps docs living and linked
- Design and build happen in parallel, not waterfall

### Kanban Columns
```
BACKLOG → IN PROGRESS → REVIEW → DONE
```

### Rituals (Lightweight)
| Ritual | Frequency | What |
|---|---|---|
| Daily standup (self) | Daily | 5 min: what did I ship, what's blocked |
| Review checkpoint | End of each phase | Demo to yourself, record a Loom, note gaps |
| Qurious demo | End of Phase 2 and Phase 4 | Show working software to client |

---

## 3. Phases and Milestones

### Phase 0: Foundation (Days 1-2) — DONE
**Goal:** Repo, infra, and tooling ready.

- [x] Create GitHub repo (`sukaimi/sofie`, public)
- [x] Set up docs folder
- [x] Install Ollama locally (Metal acceleration on M2 Pro)
- [x] Pull Qwen 3 4B + LLaMA 3.2 Vision models
- [x] Create `docker-compose.dev.yml` (ChromaDB only for local dev)
- [x] Create `CLAUDE.md` for Claude Code
- [x] Configure OpenRouter Flux 2 Pro for image generation
- [x] Set up `.env` with all service configs

**Milestone:** Ollama responds, ChromaDB healthy, OpenRouter Flux generates images.

---

### Phase 1: Core Pipeline (Days 3-7) — DONE
**Goal:** Brief in → image out. No UI yet.

- [x] Brand memory layer (ChromaDB + brand .md ingestion)
- [x] Structured brief parser (JSON schema for image jobs)
- [x] LLM prompt engineer step (Qwen 3 4B via Ollama)
- [x] OpenRouter Flux 2 Pro image generation (replaced ComfyUI for local dev)
- [x] Pillow 8-layer text/logo compositor
- [x] Brand compliance checker (LLaMA 3.2 Vision)
- [x] Feedback loop logic (fail → regenerate, max 3 attempts → escalate)
- [x] SQLite conversation/job store (async SQLAlchemy)
- [x] Pipeline orchestrator with status callbacks
- [x] CLI test runner (`python -m backend.pipeline.cli`)

**Milestone:** Full pipeline E2E passing — Flux images generated, composited, compliance scored 7-9/10.

---

### Phase 2: Chatbot Interface (Days 8-12) — DONE
**Goal:** Chat UI that wraps the pipeline. "Talk to Sofie."

- [x] React + Tailwind frontend (brand selector + chat window)
- [x] WebSocket for real-time chat
- [x] Sofie persona system prompt (account manager tone)
- [x] Conversation memory (SQLite, per-session)
- [x] Image generation triggered by conversation context ([BRIEF_READY] tag)
- [x] Image preview cards with download button
- [x] Approval queue API endpoints
- [x] Brand selector (max 3 brands, create/delete)
- [x] Conversational brand onboarding (Sofie creates brands from chat)

**Milestone:** Chat with Sofie, describe a campaign, receive generated image in chat — working.

---

### Phase 3: Hardening (Days 13-15) — PARTIAL
**Goal:** Reliable enough to demo to Qurious.

- [x] Error handling and graceful fallbacks (compliance checker fallback)
- [x] Thinking tag stripping (Qwen 3 /no_think)
- [x] Compliance threshold tuned (6/10 pass for text-heavy compositions)
- [ ] Rate limiting for image gen
- [ ] Structured JSON logging
- [ ] Basic auth for admin/approval UI
- [ ] Load testing

**Milestone:** E2E tests: Tech QA 24/24 (100%), Marketing 4/5 (80%), Creative 4/5 (80%) — 86% overall.

---

### Phase 4: Deployment (Days 16-18) — DONE
**Goal:** Running on Vast.ai, accessible via URL.

- [x] Dockerfile (multi-stage: Node frontend build + Python runtime)
- [x] docker-compose.yml (production) + docker-compose.dev.yml (local)
- [x] deploy.sh script for GPU instances
- [x] Pushed to GitHub (sukaimi/sofie, public)
- [x] Provisioned Vast.ai RTX 3090 ($0.028/hr)
- [x] Deployed via direct install (no Docker-in-Docker on Vast.ai)
- [x] Cloudflare named tunnel → **https://sofie.codeandcraft.ai**
- [x] DNS migrated from Hostinger to Cloudflare
- [ ] Demo to Qurious Media

**Milestone:** SOFIE accessible at https://sofie.codeandcraft.ai

---

### Phase 5: Post-POC (Future)
- Multi-brand switching in chat
- Batch generation mode
- GitHub Actions CI/CD to auto-deploy on push
- White-label theming per agency
- Client-facing portal with login
- Canva/Figma export integration
- Usage analytics dashboard

---

## 4. Tools

| Tool | Purpose |
|---|---|
| Claude Code | Primary build tool |
| STITCH (Google MCP) | UI/UX design generation |
| UIUX Pro Max skill | Frontend design system for Claude Code |
| Obsidian | Living documentation vault |
| GitHub (private) | Version control + deployment source |
| Docker Compose | Local + remote orchestration |
| Ollama | LLM serving (Gemma 4 26B MoE) |
| ComfyUI | Image generation (Flux.1 Schnell) |
| ChromaDB | Brand memory / RAG |
| SQLite | Conversation + job store |
| Pillow/PIL | Text and logo compositing |
| React + Tailwind | Chat frontend |
| RunPod or Vast.ai | GPU cloud deployment |

---

## 5. Team

| Role | Who |
|---|---|
| Product owner | Sukaimi |
| Builder | Claude Code (directed by Sukaimi) |
| Design | STITCH + UIUX Pro Max (via Claude Code) |
| QA | Sukaimi (manual) + automated tests |
| Pilot client | Qurious Media |

---

## 6. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Gemma 4 26B MoE GGUF not available yet | Can't run locally | Fallback: Qwen 3 8B or Gemma 3 12B. Swap when GGUF drops. |
| Flux.1 text rendering unreliable | Bad social media graphics | All text composited via Pillow, not generated by Flux |
| Vast.ai host disappears | Service goes down | Dockerised stack, redeploy to new instance in <30 min |
| LLM hallucination in account manager role | Gives wrong info to client | Approval queue (human gate) before anything reaches brand client |
| Image gen + LLM compete for VRAM | OOM crashes | Load/unload models sequentially, or use Flux Schnell FP8 (~12GB) + smaller LLM |
| Android kills Termux background processes | N/A | Abandoned phone approach. Using GPU cloud. |

---

## 7. Cross-References

- [[02-prd]] — Product Requirements Document
- [[03-tdd]] — Technical Design Document
- [[04-design-brief]] — UI/UX Design Brief for Claude Code
- [[05-claude-md]] — Claude Code root instruction file
