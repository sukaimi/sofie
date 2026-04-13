# ENV.md — Environment Variables + API Keys
**SOFIE: Studio Orchestrator For Intelligent Execution**
**Version:** 1.0 (POC)
**Last Updated:** 2026-04-13

---

## Overview

All secrets and configuration live in `.env`. This file is gitignored.
`.env.example` is committed to the repo with empty values and instructions.

Claude Code must generate `.env.example` from this document.

---

## API Keys Required

### 1. Anthropic API Key
**Variable:** `ANTHROPIC_API_KEY`
**Used by:** Sofie, Priya, Ray, Celeste, Dana (all LLM agents)
**Purpose:** All Claude API calls — chat, vision, analysis, QA

**How to get:**
1. Go to https://console.anthropic.com
2. Sign in or create account
3. Navigate to API Keys
4. Click "Create Key"
5. Copy key — it starts with `sk-ant-`

**Format:** `sk-ant-api03-...`
**Required:** YES — nothing works without this

---

### 2. Replicate API Key
**Variable:** `REPLICATE_API_KEY`
**Used by:** Image generation client (fallback only)
**Purpose:** Flux.1 Dev image generation when no hero image is provided

**How to get:**
1. Go to https://replicate.com
2. Sign in or create account
3. Navigate to Account Settings → API Tokens
4. Click "Create token"
5. Copy token — it starts with `r8_`

**Format:** `r8_...`
**Required:** NO for POC if all jobs will have hero images provided.
             YES for production use.

---

### 3. Google AI API Key (Nano Banana Pro)
**Variable:** `GOOGLE_AI_API_KEY`
**Used by:** Image generation client (Nano Banana Pro fallback)
**Purpose:** Alternative image generation for text-heavy compositions

**How to get:**
1. Go to https://aistudio.google.com
2. Sign in with Google account
3. Click "Get API Key"
4. Create new project or select existing
5. Copy API key

**Format:** `AIza...`
**Required:** NO — only needed if Nano Banana Pro is preferred over Flux for certain jobs

---

## Application Configuration

### LLM Models
```
# Claude model identifiers
LLM_MODEL_OPUS=claude-opus-4-6
LLM_MODEL_SONNET=claude-sonnet-4-6
LLM_MODEL_HAIKU=claude-haiku-4-5-20251001
```

### Image Generation
```
# Primary image gen provider: replicate | google | none
IMAGE_GEN_PROVIDER=replicate

# Flux model on Replicate
FLUX_MODEL=black-forest-labs/flux-dev

# Nano Banana Pro model identifier
NANO_BANANA_MODEL=gemini-3-pro-image-preview

# Set to true to disable image generation entirely
# (jobs without hero images will fail gracefully)
IMAGE_GEN_DISABLED=false
```

### Pipeline
```
# Cost ceiling per job in USD
COST_CEILING_USD=2.00

# Maximum QA loop attempts before escalation
MAX_QA_ATTEMPTS=3

# Maximum user revision rounds before escalation
MAX_USER_REVISIONS=2

# Maximum asset resubmission attempts before closing job
MAX_ASSET_RESUBMISSIONS=3

# Maximum brief resubmission attempts before closing job
MAX_BRIEF_RESUBMISSIONS=3

# Maximum feedback clarification exchanges
MAX_CLARIFICATION_EXCHANGES=3
```

### File Handling
```
# Max upload size in MB
MAX_UPLOAD_SIZE_MB=50

# Max asset download size in MB
MAX_ASSET_DOWNLOAD_SIZE_MB=50

# Asset download timeout in seconds
ASSET_DOWNLOAD_TIMEOUT_S=30

# Output image format: JPG | PNG
DEFAULT_OUTPUT_FORMAT=JPG

# JPG quality (1-95)
JPG_QUALITY=92
```

### Database
```
# SQLite database path
DATABASE_URL=sqlite+aiosqlite:///./data/sofie.db
```

### Redis + Celery
```
# Redis connection
REDIS_URL=redis://redis:6379/0

# Celery broker
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

### Server
```
# FastAPI
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:3000

# File server base URL (for download links)
FILE_SERVER_BASE_URL=http://localhost:8000/files
```

### Paths
```
# Brand files directory (mounted as volume)
BRANDS_DIR=/app/brands

# Brief template file path
BRIEF_TEMPLATE_PATH=/app/briefs/brief-template.docx

# Output directory
OUTPUT_DIR=/app/output

# Temp directory for asset downloads
TEMP_DIR=/tmp/sofie
```

---

## .env.example (Claude Code must generate this file)

```env
# ═══════════════════════════════════════════
# SOFIE — Environment Variables
# Copy this file to .env and fill in values
# NEVER commit .env to git
# ═══════════════════════════════════════════

# ─── REQUIRED: API Keys ───────────────────

# Anthropic API key (Claude)
# Get from: https://console.anthropic.com → API Keys
# Format: sk-ant-api03-...
ANTHROPIC_API_KEY=

# Replicate API key (Flux image generation)
# Get from: https://replicate.com → Account Settings → API Tokens
# Format: r8_...
# Required only if IMAGE_GEN_PROVIDER=replicate
REPLICATE_API_KEY=

# Google AI API key (Nano Banana Pro)
# Get from: https://aistudio.google.com → Get API Key
# Format: AIza...
# Required only if IMAGE_GEN_PROVIDER=google
GOOGLE_AI_API_KEY=

# ─── LLM Models ───────────────────────────

LLM_MODEL_OPUS=claude-opus-4-6
LLM_MODEL_SONNET=claude-sonnet-4-6
LLM_MODEL_HAIKU=claude-haiku-4-5-20251001

# ─── Image Generation ─────────────────────

# Primary image gen provider
# Options: replicate | google | none
IMAGE_GEN_PROVIDER=replicate

FLUX_MODEL=black-forest-labs/flux-dev
NANO_BANANA_MODEL=gemini-3-pro-image-preview
IMAGE_GEN_DISABLED=false

# ─── Pipeline Limits ──────────────────────

COST_CEILING_USD=2.00
MAX_QA_ATTEMPTS=3
MAX_USER_REVISIONS=2
MAX_ASSET_RESUBMISSIONS=3
MAX_BRIEF_RESUBMISSIONS=3
MAX_CLARIFICATION_EXCHANGES=3

# ─── File Handling ────────────────────────

MAX_UPLOAD_SIZE_MB=50
MAX_ASSET_DOWNLOAD_SIZE_MB=50
ASSET_DOWNLOAD_TIMEOUT_S=30
DEFAULT_OUTPUT_FORMAT=JPG
JPG_QUALITY=92

# ─── Database ─────────────────────────────

DATABASE_URL=sqlite+aiosqlite:///./data/sofie.db

# ─── Redis + Celery ───────────────────────

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# ─── Server ───────────────────────────────

APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
FRONTEND_URL=http://localhost:3000
FILE_SERVER_BASE_URL=http://localhost:8000/files

# ─── Paths ────────────────────────────────

BRANDS_DIR=/app/brands
BRIEF_TEMPLATE_PATH=/app/briefs/brief-template.docx
OUTPUT_DIR=/app/output
TEMP_DIR=/tmp/sofie
```

---

## .gitignore Entries

Claude Code must ensure these are in `.gitignore`:

```
.env
*.env
data/
output/
/tmp/
__pycache__/
*.pyc
.DS_Store
node_modules/
dist/
.venv/
```

---

## API Key Checklist for Deployment

Before deploying to Hostinger KVM 2:

- [ ] `ANTHROPIC_API_KEY` — copied from Anthropic console
- [ ] `REPLICATE_API_KEY` — copied from Replicate (if image gen needed)
- [ ] `GOOGLE_AI_API_KEY` — copied from Google AI Studio (if Nano Banana needed)
- [ ] `FILE_SERVER_BASE_URL` — updated to production domain/IP
- [ ] `FRONTEND_URL` — updated to production domain/IP
- [ ] `DEBUG` — set to `false`
- [ ] `.env` copied to server, not committed to git
- [ ] Docker Compose volumes created
- [ ] Redis container running
- [ ] SQLite data directory writable

---

## Cost Reference

| API | Model | Input cost | Output cost |
|---|---|---|---|
| Anthropic | claude-opus-4-6 | $15.00/MTok | $75.00/MTok |
| Anthropic | claude-sonnet-4-6 | $3.00/MTok | $15.00/MTok |
| Anthropic | claude-haiku-4-5 | $0.80/MTok | $4.00/MTok |
| Replicate | flux-dev | $0.030/image | — |
| Google AI | nano-banana-pro | $0.134/image (2K) | — |

MTok = million tokens

Estimated cost per job (3 sizes, all assets provided): ~$0.52
Hard ceiling per job: $2.00 (configurable via COST_CEILING_USD)
