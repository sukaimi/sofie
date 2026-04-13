# FLOWS.md — User Flows
**SOFIE: Studio Orchestrator For Intelligent Execution**
**Version:** 1.0 (POC)
**Last Updated:** 2026-04-13

---

## Flow Overview

| Flow | Trigger | End State |
|---|---|---|
| 1. Happy path | Brief uploaded, all valid, approved first pass | Delivered |
| 2. No brief | Client opens chat without brief | Delivered (after template filled) |
| 3. Brief blocker | Required field missing | Resubmission requested |
| 4. Asset blocker | Link inaccessible or asset unusable | Resubmission requested |
| 5. Font issue | Unsupported character found | User acknowledges, proceeds |
| 6. QA loop | Internal QA fails | Auto-revised or escalated |
| 7. User revision | Client requests changes | Revised and delivered |
| 8. Revision limit | 2 revision rounds exhausted | Escalated to operator |
| 9. Operator rejection | Operator rejects output | Revision loop or escalated |
| 10. Cost ceiling | Job cost hits $2.00 | Paused, operator decides |
| 11. Escalation | Any hard limit breached | Operator intervenes |
| 12. Multi-size | 3 sizes requested | Primary first, then adapt |

---

## Flow 1 — Happy Path

```
Client opens chat
  → Sofie: "Hi! I'm Sofie, your creative account manager.
             What can I help you create today?"

Client: "I need a static banner for Instagram"
  → Sofie: "Great. Do you have a brief ready to upload?
             If not, I can send you our template."

Client uploads brief.docx
  → Sofie: "Got it. Let me review this for you."

  [Marcus: creates job JOB-xxx]
  [Brief parser: extracts all fields]

  → Sofie: "Here's what I found in your brief:
             Brand: [name]
             Platform: Instagram (1080x1080, 1080x1350)
             Key message: [message]
             Headline: [text]
             Hero image: [link]
             Logo: [link]
             Font: [link]
             Is this all correct?"

Client: "Yes, that's right"

  [Priya: validates brief — all fields present, no strategic issues]
  [Font check: all characters supported]
  [Ray: fetches and validates all assets — all OK]

  → Sofie: "Everything looks good. Starting on your visuals now."

  [Celeste: analyses layout reference, creates composition plan]
  [Kai: composites image — all layers applied]
  [Dana: QA check — all 3 pass]

  → Sofie: "Here's your Instagram square (1080x1080).
             I went with [rationale].
             Happy with it, or would you like changes?
             [Guided feedback menu]"

Client: "Love it. Approved!"

  → Sofie: "Wonderful. Let me adapt this for your 1080x1350 portrait size."

  [Kai: adapts composition to new dimensions]
  [Dana: QA check — pass]

  → Sofie: "Portrait version is ready too. Sending both to the team for final sign-off."

  [Operator dashboard: job appears for Noel]
  [Noel: reviews, approves]

  → Sofie: "Approved! Here are your files:
             [Download link]
             Job complete."
```

---

## Flow 2 — No Brief

```
Client: "Hi, I need some social media graphics"
  → Sofie: "Happy to help. To get started, I'll need a brief from you.
             Do you have our template?"

Client: "No, what template?"
  → Sofie: "No problem. Here's the link to download our brief template:
             [Download link]
             Fill in as much as you can — I'll flag anything missing.
             Upload it here when ready."

Client: [uploads completed brief]
  → [Continue from Flow 1: brief extraction step]
```

---

## Flow 3 — Brief Blocker

```
[Brief parser extracts fields]
[Priya: finds missing required field — e.g. no logo link]

  → Sofie: "I've reviewed your brief and found an issue before we can proceed:

             REQUIRED — Missing:
             Logo: No logo link was provided. I need a logo file to continue.
             Please share a link to your logo (SVG preferred, or PNG with
             transparent background, minimum 500x500px).

             Once you've updated your brief, please re-upload it and I'll
             continue from there."

Client: [uploads revised brief]
  → [Brief re-parsed, re-validated]
  → [If clear: continue]
  → [If still blocked: repeat, count resubmission attempt]

[After 3 resubmission attempts:]
  → Sofie: "We've tried a few times and I'm still unable to proceed.
             Let me flag this to the team for some extra help.
             Someone will be in touch shortly."
  → [Escalate to operator]
```

---

## Flow 4 — Asset Blocker

```
[Ray: fetches logo link — returns 403 Forbidden]

  → Sofie: "I tried to access your logo but hit a permissions issue:

             Logo link: [url]
             Error: This Google Drive link is restricted.
             Fix: Please change the sharing settings to
             'Anyone with the link can view' and resend.

             Once fixed, you can paste the corrected link here
             and I'll continue."

Client: [pastes new link]
  → [Ray: re-fetches single asset]
  → [If OK: continue]
  → [If still blocked: count attempt, report again]

[Unusable asset — wrong format:]
  → Sofie: "I received your logo, but I can't use this file:

             Logo: [filename]
             Issue: This appears to be a JPEG file with a white background.
             I need the logo as an SVG or PNG with a transparent background
             so it can be properly placed on the design.

             Most brand kits include a transparent PNG version.
             Could you check with your team and resubmit?"
```

---

## Flow 5 — Font Character Issue

```
[Font check: headline contains é — not in brand font]

  → Sofie: "Quick heads up before I start compositing:

             Your brand font doesn't support the character 'é'
             in your headline: '[headline text]'

             I can either:
             1. Use a fallback system font for that character only
                (may look slightly different from the rest of the text)
             2. You can rephrase the headline to avoid the character

             Which would you prefer?"

Client: "Use the fallback"
  → Sofie: "Got it. I'll note that in the job and proceed."
  → [Continue pipeline with fallback flag set]

Client: "I'll rephrase"
  → Sofie: "Of course. What would you like the headline to say?"
  → [Client provides new headline, update brief, continue]
```

---

## Flow 6 — QA Loop

```
[Kai composites image]
[Dana QA: Check 2 fails — headline not visible enough, score 62]

  → [Celeste: receives Dana's revision notes]
  → [Celeste: adjusts text element — increases font size, increases contrast]
  → [Kai: recomposites]
  → [Dana QA: all 3 pass — score 88]

  → Sofie: [presents image to client]

[If QA fails 3 times:]
  → Marcus: sets status to "escalated", reason "qa_failed"
  → Sofie: "I've made several attempts to get this right but
             my quality check keeps flagging issues.
             I'm sending this to the team for a closer look.
             They'll review and come back to you shortly."
  → [Operator dashboard: job appears with qa_failed flag]
```

---

## Flow 7 — User Revision

```
[Sofie presents output]
[Guided feedback menu shown]

Client: "The headline is too small and the logo should be bottom right"

  [Sofie evaluates feedback:]
  → "Move logo to bottom right" = ACTIONABLE
  → "Headline too small" = ACTIONABLE

  → Sofie: "Got it. Making those changes now — bigger headline,
             logo to bottom right."

  [Celeste: updates composition plan]
  [Kai: recomposites]
  [Dana QA: pass]

  → Sofie: [presents revised image]
           "Revised. Happy with this version?"

Client: "Yes!"
  → [Continue to operator approval]
```

---

## Flow 8 — Vague Feedback

```
Client: "Make it pop more"

  [Sofie evaluates: VAGUE feedback]

  → Sofie: "I want to make sure I get this right.
             When you say 'pop more' — do you mean the colours
             feel too muted? I can increase the contrast and
             brighten the overlay tint. Does that sound right?"

Client: "Yes exactly"
  → [Revise with increased contrast]

Client: "No, more like the layout feels flat"
  → Sofie: "Ah, a layout issue — understood. Would you like me
             to increase the size of the hero image or add more
             visual separation between the text and image areas?"
```

---

## Flow 9 — Revision Limit

```
[Round 1 revision complete — presented]
[Round 2 revision complete — presented]

Client: "Still not right. Can you try again?"

  → Sofie: "I've done my best across two rounds of revisions.
             To make sure you get exactly what you need,
             I'm passing this to the team for a closer look.
             They'll review and come back to you with options."

  → Marcus: sets user_revision_count = 2, triggers escalation
  → Operator dashboard: job appears with "revision_limit" flag
  → Noel: reviews, decides whether to continue or close
```

---

## Flow 10 — Operator Rejection

```
[Job sent to operator dashboard]
[Noel: reviews — rejects with notes:
 "Logo is too large and dominant. Reduce to 12% canvas width.
  Text colour needs more contrast against the background."]

  → Sofie receives operator notes
  → Sofie: "The team reviewed your visual and flagged a couple
             of things to tighten up before we send it over.
             I'm making those adjustments now."

  [Celeste + Kai: revise per operator notes]
  [Dana QA: pass]

  → Sofie: [presents revised image]
  → Operator: approves
  → Delivery
```

---

## Flow 11 — Cost Ceiling

```
[Running cost reaches $2.00]
[Marcus: pauses job, sets status to "escalated", reason "cost_ceiling"]

  → Sofie: "I've paused work on your job for a moment —
             this one is taking a bit more processing than usual.
             The team is reviewing and will continue shortly."

  → Operator dashboard: job appears with "cost_ceiling" flag
  → Noel: reviews — decides to extend budget or close job

  [If extend:]
  → Marcus: increases ceiling to $3.00
  → Pipeline resumes

  [If close:]
  → Sofie: "The team has reviewed this job and we'd like to
             discuss the best approach with you. Someone will
             be in touch directly."
```

---

## Flow 12 — Multi-Size

```
[Brief specifies 3 sizes:
 1080x1080 (Instagram square)
 1080x1350 (Instagram portrait)
 1200x628 (LinkedIn landscape)]

  → Sofie: "You've requested 3 sizes. I'll start with the
             Instagram square (1080x1080) — it's the most
             complex canvas and gives us the best foundation
             to adapt from. I'll show you that one first."

  [Full pipeline runs for 1080x1080]
  [Client approves]

  → Sofie: "Great. Adapting now for your 1080x1350 portrait..."
  [Kai: adapts composition — adjusts proportions for taller canvas]
  [Dana QA: pass]
  → Sofie: [presents portrait version]
           "This works well vertically. Happy?"

Client: "Can you move the logo up slightly?"
  → [Revision round 1 for portrait size]
  → Sofie: [presents revised portrait]

Client: "Perfect"
  → Sofie: "And finally, your LinkedIn landscape (1200x628)..."
  [Kai: adapts — wider canvas, adjusted hierarchy]
  [Dana QA: pass]
  → Sofie: [presents LinkedIn version]

Client: "Love it"
  → [All 3 sizes sent to operator]
  → [Operator approves]
  → Sofie: "All three are approved. Here are your files:
             [Download link — all 3 sizes in one package]"
```

---

## Sofie Tone Reference

| Situation | Tone | Example |
|---|---|---|
| Greeting | Warm, inviting | "Hi! I'm Sofie, your creative account manager." |
| Progress update | Calm, confident | "Creating your visual now..." |
| Presenting work | Proud, explanatory | "Here's your banner. I went with warm gold tones to match your brief." |
| Reporting a blocker | Clear, specific, helpful | "I need your logo as a PNG with transparent background." |
| Handling vague feedback | Curious, guiding | "When you say 'pop more' — do you mean the colours feel too muted?" |
| Escalating | Calm, reassuring | "I'm flagging this to the team for a closer look." |
| Delivering | Warm, conclusive | "All approved. Here are your files. Great working with you." |
