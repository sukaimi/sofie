# SOFIE — Improvement Backlog

Last updated: 2026-04-20

| # | Priority | Status | Item | Category |
|---|----------|--------|------|----------|
| 1 | P0 | DONE | Sub-copy hallucination — text sanitised against brief content | Bug |
| 2 | P3 | TODO | Logo bg removal — strip white/dark bg from PDF-rendered logos | Quality |
| 3 | P0 | DONE | Text contrast backing — rounded dark backing at 55% opacity behind text | Quality |
| 4 | P1 | TODO | Celeste text element reliability — frequently returns empty, relies on fallback | Pipeline |
| 5 | P1 | TODO | Flux prompt quality — feed more brief context for relevant hero images | Quality |
| 6 | P1 | TODO | Brand colour integration — use extracted colours in overlay/accents | Quality |
| 7 | P1 | TODO | Google Drive reference links — still downloading HTML pages | Bug |
| 8 | P1 | TODO | Auto-trigger re-run when Sofie promises it | UX |
| 9 | P2 | TODO | Font matching from guidelines — match extracted name to Google Fonts | Quality |
| 10 | P2 | TODO | Sofie hallucination on edge cases — shorter max_tokens for errors | Bug |
| 11 | P2 | TODO | QA loop cost vs value — consider 1 pass max, show result + suggestions | Pipeline |
| 12 | P2 | TODO | Move pipeline to Celery async — WebSocket timeout risk | Pipeline |
| 13 | P2 | TODO | Conversation state persistence on page refresh | UX |
| 14 | P3 | TODO | Multiple output sizes from brief | UX |
| 15 | P3 | TODO | ZIP download for multiple sizes | UX |
| 16 | P3 | TODO | Cost tracking accuracy — verify vs actual billing | Pipeline |
| 17 | P3 | TODO | Replicate API monitoring — log time and cost per image | Infra |
| 18 | P3 | TODO | Health check endpoint — DB, Redis, Anthropic connectivity | Infra |
| 19 | P3 | TODO | Structured logging with job_id context | Infra |
| 20 | P3 | TODO | Persistent upload volume | Infra |
| 21 | P3 | TODO | Error reporting — traceable errors | Infra |

**P0** = must fix before next demo
**P1** = high impact, next session
**P2** = important but not blocking
**P3** = nice to have

## v1+ / media

- Pexels video source + video compositing — requires new render pipeline (out of POC scope).
