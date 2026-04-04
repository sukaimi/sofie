# SOFIE — Product Requirements Document
**Smart Output Factory for Image Execution**
**Version:** 1.0
**Owner:** Code&Canvas Pte Ltd
**Client:** Qurious Media (pilot)
**Last Updated:** 2026-04-04

---

## 1. Problem Statement

Social media agencies managing 100+ brands spend significant time on repetitive creative production: receiving briefs, interpreting brand guidelines, generating visuals, applying brand elements, and managing revision cycles. The current workflow is manual, slow, and doesn't scale.

Qurious Media manages ~250 brands with ~6 statics per brand per month (1,500 deliverables/month). Two people handle QC. The bottleneck is human bandwidth, not creative capability.

---

## 2. Solution

SOFIE is an AI-powered creative account manager chatbot. Brand clients (or agency staff) interact with Sofie via a web chat interface. Sofie understands the brand, takes a brief conversationally, generates brand-compliant social media images, and manages the revision cycle.

All processing runs on self-hosted open-source models. Zero API token costs.

---

## 3. POC Scope

**In scope:**
- Web-based chat interface (embeddable)
- AI account manager persona ("Sofie")
- Conversational brief intake (not form-based)
- Single image output per conversation turn
- JPG/PNG output
- Brand context loaded via RAG (ChromaDB)
- Text and logo compositing via Pillow (not model-generated)
- Approval queue for Qurious team
- Runs on GPU cloud (RunPod/Vast.ai)
- English only

**Out of scope (future):**
- Batch processing
- Video output
- Multi-language
- Canva/Figma export
- Client login portal
- Usage analytics
- White-label theming engine

---

## 4. User Roles

| Role | Description | Access |
|---|---|---|
| Brand Client | Talks to Sofie, submits briefs, reviews output | Chat UI only |
| Agency Operator | Qurious team member, approves/rejects before delivery | Approval dashboard |
| Admin | Manages brands, uploads guidelines, configures Sofie | Admin panel (future) |

---

## 5. User Flows

### Flow 1: Brief to Image (Happy Path)
```
Client opens chat
  → Sofie greets, asks what they need
  → Client describes campaign ("5 IG posts for Hari Raya, warm tones, family focus")
  → Sofie asks clarifying questions (dimensions, key messages, must-include elements)
  → Sofie confirms brief as structured JSON (internal)
  → Sofie generates image via pipeline
  → Sofie presents draft in chat
  → Client says "love it" or "make the text bigger"
  → If revision: Sofie adjusts and regenerates
  → If approved: image goes to approval queue
  → Qurious operator reviews and releases to client
```

### Flow 2: Revision Loop
```
Client requests change
  → Sofie parses feedback into actionable adjustment
  → Re-runs relevant pipeline step (compositor only if text change, full regen if concept change)
  → Presents updated draft
  → Max 3 auto-revisions, then escalates to Qurious operator
```

### Flow 3: Approval Gate
```
Sofie generates final image
  → Image + metadata pushed to approval queue
  → Qurious operator sees: brand name, brief summary, generated image, compliance score
  → Operator approves → client notified, image available for download
  → Operator rejects → sends back with notes → Sofie re-enters revision loop
```

---

## 6. Sofie Persona

**Role:** Creative Account Manager
**Tone:** Friendly, professional, proactive. Not robotic. Not overly casual.
**Behaviour:**
- Greets warmly, asks what they need
- Asks smart clarifying questions (doesn't just accept vague briefs)
- Confirms understanding before generating
- Presents work with brief rationale ("I went with warm gold tones to match your Hari Raya brief")
- Handles rejection gracefully ("Got it, let me adjust. Bigger headline, same layout?")
- Never lies about capabilities ("I can't do video yet, but I can create a strong static for that")

**System prompt structure:**
```
You are Sofie, a creative account manager at [agency name].
You help brand clients create social media visuals.
You have access to the brand's visual identity guidelines (loaded via context).
You ask clarifying questions before generating.
You present work with brief rationale.
You handle revisions patiently (max 3 before escalating).
You never fabricate brand information — only use what's in the brand context.
```

---

## 7. Pipeline Architecture

```
CONVERSATION LAYER (Gemma 4 / LLM)
  ↓
BRIEF PARSER (structured JSON extraction)
  ↓
BRAND MEMORY (ChromaDB RAG — brand .md, assets, past briefs)
  ↓
PROMPT ENGINEER (LLM generates image gen prompt from brief + brand context)
  ↓
IMAGE GENERATOR (Flux.1 Schnell via ComfyUI API)
  ↓
COMPOSITOR (Pillow — text overlays, logo, brand elements)
  ↓
COMPLIANCE CHECKER (LLM vision mode — checks output vs brand guidelines)
  ↓ pass/fail
APPROVAL QUEUE (Qurious operator reviews)
  ↓ approved
DELIVERY (image available in chat + download)
```

---

## 8. Inputs Per Brand

| Input | Format | Required | Stored In |
|---|---|---|---|
| Brand summary | .md | Yes | ChromaDB + filesystem |
| Logo | SVG or PNG (transparent) | Yes | `/brands/{name}/assets/` |
| Brand fonts | OTF or TTF | Yes | `/brands/{name}/assets/` |
| Colour palette | In brand.md | Yes | ChromaDB |
| Hero images | JPG/PNG | Optional | `/brands/{name}/assets/images/` |
| Design elements | SVG/PNG | Optional | `/brands/{name}/assets/elements/` |
| Style references | JPG/PNG | Optional | `/brands/{name}/assets/references/` |
| Brand positioning | .md | Optional | ChromaDB |
| Past approved outputs | JPG/PNG | Optional (grows over time) | `/brands/{name}/approved/` |

---

## 9. Structured Brief Schema (Internal)

When Sofie extracts a brief from conversation, it produces:

```json
{
  "job_id": "JOB-20260404-001",
  "brand": "brand-name",
  "platform": "instagram",
  "dimensions": "1080x1080",
  "campaign": "Hari Raya 2026",
  "key_message": "Family togetherness",
  "tone": "warm, celebratory",
  "must_include": ["logo", "tagline", "product shot"],
  "must_avoid": ["competitor colours", "alcohol imagery"],
  "text_overlays": [
    {"text": "Selamat Hari Raya", "position": "top-centre", "style": "headline"},
    {"text": "From our family to yours", "position": "bottom-centre", "style": "subhead"}
  ],
  "image_gen_prompt": null,
  "model": "flux-schnell",
  "status": "pending"
}
```

The `image_gen_prompt` field is populated by the Prompt Engineer step, not by the client.

---

## 10. Success Criteria (POC)

- [ ] Client can chat with Sofie and describe a creative need conversationally
- [ ] Sofie asks at least 2 clarifying questions before generating
- [ ] Pipeline produces a brand-compliant image with correct logo and text
- [ ] Revision loop works (client feedback triggers targeted regeneration)
- [ ] Approval queue shows pending items to Qurious operator
- [ ] Full cycle completes in under 3 minutes
- [ ] 10 consecutive runs without failure
- [ ] Runs on GPU cloud accessible via URL

---

## 11. Known Limitations (POC)

- Single image per conversation turn (no batch)
- No video
- Flux.1 cannot render text reliably — all text applied via Pillow
- Brand compliance checker may produce false positives on abstract/artistic styles
- LLM may hallucinate brand details if brand.md is incomplete — mitigation: strict RAG, no freeform knowledge
- Image generation takes 10-30 seconds depending on GPU load
- No client authentication (anyone with the URL can chat)

---

## 12. Previous Build (Archived)

A prior version of this project was built under the name "POC Creative Studio" with a different product shape (manual pipeline trigger, 8-agent architecture, no chatbot interface). All documentation from that build has been moved to the `archived/` folder in the project vault.

**What was built previously:**
- PRD v0.2 (8-step pipeline, model-agnostic image gen adapter)
- Brand summary, brief, and positioning templates (.md)
- 8-agent architecture (Account Director, Traffic Manager, Art Director, Creative Designer, Creative Director, Production Studio, Brand Compliance Checker, Output Packager)
- Model routing logic (Nano Banana Pro, Flux.1 Dev, Flux.1 Schnell)
- Folder structure and schema definitions
- No code was written. Docs only.

**What carries forward into SOFIE:**
- Brand summary and brief templates (reuse as-is for brand onboarding)
- Pillow compositing approach (text/logo overlay, not model-generated)
- Brand compliance checker concept (vision LLM review)
- Flux.1 Schnell as default image gen model
- Max 3 regeneration loop cap

**What does NOT carry forward:**
- 8-agent architecture (replaced by single Sofie persona + pipeline steps)
- Manual pipeline trigger (replaced by conversational chatbot)
- Nano Banana Pro as default image gen (replaced by Flux.1 Schnell for commercial licensing clarity)
- Local-only execution (replaced by GPU cloud deployment)
- OpenClaw as orchestrator (replaced by standalone FastAPI app)

**Claude Code instruction:** If you need context on past design decisions, read the archived docs. Do not build from them. Build from this PRD (v1.0) and the TDD ([[03-tdd]]).

---

## 13. Cross-References

- [[01-project-plan]] — Project Plan
- [[03-tdd]] — Technical Design Document
- [[04-design-brief]] — UI/UX Design Brief
- [[05-claude-md]] — Claude Code Instruction File
