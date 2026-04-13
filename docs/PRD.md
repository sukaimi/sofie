# PRD.md — Product Requirements Document
**SOFIE: Studio Orchestrator For Intelligent Execution**
**Version:** 1.0 (POC)
**Owner:** Code&Canvas Pte Ltd
**Last Updated:** 2026-04-13

---

## 1. Problem Statement

Social media agencies managing 100+ brands spend significant time on repetitive creative production. The current workflow is manual, slow, inconsistent, and does not scale. The bottleneck is human bandwidth applied to low-complexity, high-volume work.

The core pain points are:
- Inconsistent brand compliance across freelancers
- High QC burden on a small team
- Slow revision cycles
- No institutional memory between jobs

---

## 2. What SOFIE Is

SOFIE is an AI-powered creative composition engine with a conversational front-end. It is not an image generator. It takes provided brand assets, interprets a creative brief, composes a brand-compliant static image, QAs it internally, and delivers it — all through a chat interface managed by an AI account manager named Sofie.

---

## 3. POC Scope

**In scope:**
- Web chat interface (desktop browser)
- AI account manager persona (Sofie)
- .docx brief upload and parsing
- Asset link fetching and validation
- Vision-based asset identification
- Proportional layout analysis from sample references
- Image composition via Pillow
- Typography rendering via Cairo + Pango
- Internal QA (3 checks)
- Human operator approval dashboard
- Download link delivery
- Up to 3 output sizes per brief
- English only
- Sequential job processing

**Out of scope (v1+):**
- Batch processing
- Video output
- Multi-language
- Google Drive delivery
- Client login portal
- Usage analytics
- White-label theming
- Parallel job processing
- ChromaDB / RAG brand memory
- Full 12-agent roster

---

## 4. Users

| Role | Description | Interface |
|---|---|---|
| Brand client | Submits brief, reviews output, gives feedback | Chat UI |
| Agency operator | Reviews, approves or rejects output | Streamlit dashboard |
| Admin | Code&Canvas — configures, monitors, deploys | Server + .env |

---

## 5. The Brief Template (.docx)

The brief is the primary input. SOFIE provides a downloadable `.docx` template. The brand fills it and uploads it to chat.

**Template sections:**

**Section 1 — Brand Information**
- Brand name (required)
- Industry (required)
- Brand guidelines link (optional — Google Drive, Dropbox, or direct URL)

**Section 2 — Job Details**
- Job title (required)
- Platform(s): Instagram / Facebook / LinkedIn (required)
- Output sizes — up to 3 (required, e.g. 1080x1080, 1080x1350, 1200x628)

**Section 3 — Campaign Context**
- Campaign objective (required)
- Key message — one sentence (required)
- Call to action text (optional)

**Section 4 — Asset Links**
- Logo link (required — SVG or PNG with transparent background)
- Brand font link (required — OTF or TTF)
- Hero image link(s) (optional — JPG or PNG, high resolution)
- Design elements link(s) (optional — patterns, textures, frames)
- Brand colour palette (required — hex codes or link to guidelines)

**Section 5 — Layout References**
- Own past ad link(s) (optional — "replicate this layout")
- External layout reference link(s) (optional — "extract structure only")
- Mood reference link(s) (optional — "capture this feeling")
- Classification must be stated per link

**Section 6 — Copy**
- Headline text (required)
- Sub-copy (optional)
- Mandatory inclusions (optional — legal text, disclaimers)

**Section 7 — Restrictions**
- What not to do (optional)
- Colours to avoid (optional)
- Elements to avoid (optional)

---

## 6. Asset Specifications

| Asset | Format | Min Spec | Notes |
|---|---|---|---|
| Logo | SVG (preferred) or PNG | PNG min 500x500px | Must have transparent background |
| Font | OTF or TTF | — | Must cover Latin character set |
| Hero image | JPG or PNG | Min 1080px on shortest side | Higher res preferred |
| Design elements | SVG or PNG | Min 500px | Transparent background if needed |
| Layout references | JPG or PNG | Min 800px | Any aspect ratio |

---

## 7. Field Classification

| Field | Classification | If Missing |
|---|---|---|
| Brand name | BLOCKER | Cannot proceed |
| Key message | BLOCKER | Cannot proceed |
| Output size(s) | BLOCKER | Cannot proceed |
| Logo link | BLOCKER | Cannot proceed |
| Brand font link | BLOCKER | Cannot proceed |
| Brand colours | BLOCKER | Cannot proceed |
| Headline text | BLOCKER | Cannot proceed |
| Platform | BLOCKER | Cannot proceed |
| Campaign objective | WARNING | Proceed, note assumption |
| CTA text | OPTIONAL | Omit from composition |
| Hero image | OPTIONAL | Flux generates base image |
| Design elements | OPTIONAL | Flux generates if brand style clear |
| Layout references | OPTIONAL | Celeste decides layout |
| Sub-copy | OPTIONAL | Omit from composition |
| Restrictions | OPTIONAL | Proceed without |

---

## 8. Asset Validation Rules

### Link accessibility
- Link must be publicly accessible (no login required)
- Link must not be expired
- File must be downloadable within 30 seconds
- If inaccessible: BLOCKER — stop, tell user exact error, advise fix

### Asset usability
| Asset | Failure Condition | Classification | Advice to User |
|---|---|---|---|
| Logo | Under 500px, no transparency, wrong format | BLOCKER | "Please provide SVG or high-res PNG with transparent background, min 500x500px" |
| Font | Cannot be loaded by Cairo | BLOCKER | "Please provide OTF or TTF font file" |
| Hero image | Under 1080px shortest side | WARNING | "Image may appear low quality. Proceeding but recommend higher resolution" |
| Design elements | Cannot be parsed as image | WARNING | "Could not read this file. Proceeding without it" |
| Any link | Restricted / expired | BLOCKER | Specific message per platform (Google Drive, Dropbox, WeTransfer) |

---

## 9. Font + Character Check

Before composition begins:
- Load brand font via Cairo
- Scan all text in brief (headline, sub-copy, CTA, mandatory text)
- Check each character against font's character set
- If unsupported characters found: flag immediately in chat with specific characters listed
- Ask user to acknowledge before proceeding or rephrase
- Apply system fallback font for unsupported characters only if user acknowledges

---

## 10. Layout Intelligence

Celeste analyses layout references using Claude Opus vision.

**Reference classification:**

| Type | User labels as | Celeste behaviour |
|---|---|---|
| Own past ad | "Replicate this" | Copy layout structure closely |
| External brand | "Layout reference" | Extract spatial structure only, not style |
| Mood reference | "Mood reference" | Extract tone, feeling, energy |

**Proportional layout extraction:**
- Celeste extracts element positions as proportions of canvas (not pixels)
- Example: "Logo occupies bottom-right quadrant, 15% canvas width, 5% margin from edges"
- Translates to absolute pixels per output dimension
- First-pass accuracy: 60-70% — QA loop and revision cover the rest

**If no layout reference provided:**
- Celeste analyses brand guidelines .md and hero image
- Applies compositional best practice for platform/format
- Documents reasoning in job log

**Online reference search:**
- If brand provides category/style descriptor but no reference image
- Celeste may use web search to find relevant layout examples
- Only extracts structure — never style, brand identity, or copy from external sources

---

## 11. Composition Layer Order

Kai executes layers bottom to top using Pillow:

1. Background colour or gradient (from brand palette)
2. Colour overlay / tint (if specified)
3. Brand pattern / texture (if provided)
4. Hero image (client-provided or Flux-generated)
5. Design elements (frames, graphic devices)
6. Logo (position per brand guide or Celeste's plan)
7. Headline text (Cairo + Pango, brand font, brand colour)
8. Sub-copy (Cairo + Pango, brand font, lighter weight)
9. CTA text (Cairo + Pango, brand font, accent colour)
10. Mandatory text (Cairo + Pango, smallest size, legal placement)

---

## 12. Internal QA — 3 Checks

Dana runs all 3 checks on the composited image via Claude Sonnet vision.

**Check 1: Layout quality**
- Visual hierarchy correct (hero dominant, logo secondary, text readable)
- Elements balanced and properly spaced
- No awkward overlaps or clipping at edges
- Negative space used well

**Check 2: Brief compliance**
- Correct headline present and readable
- CTA present if specified in brief
- Mood/tone matches brief description
- Layout reference honoured (if provided)
- No restricted elements present

**Check 3: Technical specification**
- Output dimensions exactly correct
- File format correct (JPG or PNG)
- Resolution meets platform minimum
- Logo at correct proportional size
- No element clipping at canvas edges
- Text legible at intended display size

**QA output:**
```json
{
  "check1_layout": {"pass": true, "score": 85, "issues": []},
  "check2_brief": {"pass": true, "score": 90, "issues": []},
  "check3_spec": {"pass": true, "score": 100, "issues": []},
  "overall_pass": true,
  "recommendation": "send_to_user"
}
```

**Loop logic:**
- All 3 pass → send to user
- Any fail → Celeste + Kai revise → Dana re-checks (max 3x total)
- 3x fail → escalate to operator with flag, do not send to user

---

## 13. User Feedback Handling

Sofie presents output with a guided feedback menu:

> "Here's your [size] for [platform]. Happy with it, or would you like changes?
> If changes, tell me what to adjust:
> 1. Text — wording, size, or position
> 2. Layout — element arrangement or spacing
> 3. Logo — size or position
> 4. Image — crop or focus area
> 5. Colours — overlay, tint, or contrast
> 6. Something else — describe it"

**Feedback evaluation (Sofie + LLM):**

| Type | Example | Action |
|---|---|---|
| ACTIONABLE | "Move logo to bottom right" | Proceed with revision |
| VAGUE | "Make it pop more" | Ask one targeted clarifying question |
| UNACTIONABLE | "Redo it completely" | Ask user to use guided menu |
| CONTRADICTORY | "Remove the logo" | Flag conflict with brief/brand guidelines, confirm |

**Clarification rules:**
- One question at a time
- Sofie suggests what she thinks user means, user confirms
- Clarification exchanges do not count as revision rounds

**Revision rounds:**
- Round 1 → revise → QA → present
- Round 2 → revise → QA → present
- No round 3 → escalate to operator

---

## 14. Multi-Size Handling

- Brief specifies up to 3 sizes
- Sofie selects primary size (most complex canvas) and states why
- Generates and validates primary size first
- User approves primary → Sofie adapts to remaining sizes
- 1-2 revisions per additional size
- Each size goes through full QA
- All sizes delivered together in final download

---

## 15. Cost Management

- Track token usage per agent per job in SQLite
- Calculate cost after each agent call
- Running total visible in job log
- Hard ceiling: $2.00 per job
- If ceiling breached: pause job immediately, alert operator, do not continue
- Operator decides: extend budget or close job

---

## 16. Operator Dashboard

Single Streamlit page. One job card per pending approval.

**Card contains:**
- Brand name, job title, date, platform
- All output size previews
- Brief summary (key message, CTA, sizes)
- QA scores per check (layout, brief, spec)
- Cost so far
- Agent log (which agent did what, any issues)

**Actions:**
- Approve → trigger download link generation, notify Sofie
- Reject with notes → notes sent to Sofie as operator feedback → revision loop
- Extend budget → increase cost ceiling for this job

---

## 17. Delivery

On operator approval:
- Final JPG/PNG files packaged
- Download link generated (served from VPS)
- Sofie sends link to user in chat
- Job status set to "delivered"
- Cost summary logged

---

## 18. Loop Protection Matrix

| Loop Type | Max | On Breach |
|---|---|---|
| Internal QA auto-revision | 3 | Escalate to operator |
| User revision rounds | 2 | Escalate to operator |
| Feedback clarification exchanges | 3 | Ask user to restart |
| Asset resubmission attempts | 3 | Close job, ask user to restart |
| Brief resubmission attempts | 3 | Close job, ask user to restart |
| Cost ceiling breach | $2.00 | Pause, alert operator |

---

## 19. Success Criteria (POC)

- [ ] .docx brief uploads and extracts cleanly
- [ ] Asset links fetch and validate correctly
- [ ] Vision correctly identifies asset types
- [ ] Font check flags unsupported characters before generation
- [ ] Composition layers correctly in correct order
- [ ] Cairo + Pango renders headline text at brand-quality typography
- [ ] QA returns meaningful pass/fail with scores
- [ ] User revision loop works for 2 rounds
- [ ] Operator dashboard shows correct job info
- [ ] Download link delivers correct files
- [ ] Cost tracking logs correctly per agent
- [ ] 10 consecutive E2E runs complete without crash

---

## 20. Known Limitations (POC)

- .docx text boxes and embedded objects may not extract — flag to user
- Layout intelligence first-pass accuracy ~60-70%
- Sequential processing only — no parallel jobs
- No Google Drive delivery — download link only
- No client login — URL access only
- No job history or brand memory (file-based only)
- No batch processing
- English only
