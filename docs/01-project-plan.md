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

### Phase 0: Foundation (Days 1-2)
**Goal:** Repo, infra, and tooling ready.

- [ ] Create private GitHub repo (`sofie`)
- [ ] Set up Obsidian vault with docs (this folder)
- [ ] Install Docker Desktop locally
- [ ] Create `docker-compose.yml` (Ollama + ComfyUI + SOFIE app)
- [ ] Install Ollama locally, pull Gemma 4 26B MoE (or fallback model)
- [ ] Install ComfyUI locally, download Flux.1 Schnell
- [ ] Verify both run and respond
- [ ] Create `claude.md` for Claude Code
- [ ] Install UIUX Pro Max skill (`uipro init --ai claude`)

**Milestone:** `ollama run gemma4:26b-a4b` returns a response. ComfyUI generates a test image.

---

### Phase 1: Core Pipeline (Days 3-7)
**Goal:** Brief in → image out. No UI yet.

- [ ] Brand memory layer (ChromaDB + brand .md ingestion)
- [ ] Structured brief parser (JSON schema for image jobs)
- [ ] LLM prompt engineer step (Gemma 4 reads brand context + brief → image prompt)
- [ ] ComfyUI API integration (send prompt → receive image)
- [ ] Pillow text/logo compositor (overlay brand elements post-generation)
- [ ] Brand compliance checker (Gemma 4 vision mode reviews output)
- [ ] Feedback loop logic (fail → regenerate, max 3 attempts → escalate)
- [ ] SQLite conversation/job store
- [ ] Unit tests for each step

**Milestone:** Run `python pipeline.py --brand test-brand --brief test-brief` and get a brand-compliant image in `/output/`.

---

### Phase 2: Chatbot Interface (Days 8-12)
**Goal:** Chat UI that wraps the pipeline. "Talk to Sofie."

- [ ] Design brief created for STITCH + UIUX Pro Max (see [[04-design-brief]])
- [ ] React frontend (embeddable chat widget)
- [ ] WebSocket or SSE for streaming responses
- [ ] Sofie persona system prompt (account manager tone, proactive clarification)
- [ ] Conversation memory (SQLite, per-session + cross-session)
- [ ] Image generation triggered by conversation context (not explicit commands)
- [ ] Approval queue UI (Streamlit or simple admin page for Qurious team)
- [ ] Integration tests

**Milestone:** Open browser, chat with Sofie, describe a campaign, receive generated image in chat.

---

### Phase 3: Hardening (Days 13-15)
**Goal:** Reliable enough to demo to Qurious.

- [ ] Error handling and graceful fallbacks
- [ ] Circuit breaker (if local model fails, fallback to Google AI Studio free tier)
- [ ] Rate limiting for image gen
- [ ] Logging (structured JSON logs)
- [ ] Basic auth for admin/approval UI
- [ ] Load testing (simulate 5 concurrent chats)
- [ ] Bug fixes from Phase 2 testing

**Milestone:** 10 consecutive end-to-end runs without failure.

---

### Phase 4: Deployment (Days 16-18)
**Goal:** Running on Vast.ai/RunPod, accessible via URL.

- [ ] Dockerise entire stack (multi-container compose)
- [ ] Push to GitHub
- [ ] Provision RunPod/Vast.ai GPU instance (RTX 3090, 24GB VRAM)
- [ ] Deploy via Docker Compose on GPU instance
- [ ] Cloudflare Tunnel or direct URL for access
- [ ] Verify full pipeline works on remote infra
- [ ] Document update/redeploy process (GitHub push → SSH → docker compose pull)
- [ ] Demo to Qurious Media

**Milestone:** Qurious can access SOFIE via a URL, chat with Sofie, and receive images.

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
