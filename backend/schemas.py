from datetime import datetime

from pydantic import BaseModel, Field


# --- Brief ---


class TextOverlay(BaseModel):
    text: str
    position: str  # top-centre, bottom-centre, etc.
    style: str  # headline, subhead, body, cta


class BriefSchema(BaseModel):
    job_id: str | None = None
    brand: str
    platform: str = "instagram"
    dimensions: str = "1080x1080"
    campaign: str | None = None
    key_message: str | None = None
    tone: str | None = None
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    text_overlays: list[TextOverlay] = Field(default_factory=list)
    image_gen_prompt: str | None = None
    model: str = "flux-schnell"
    status: str = "pending"


class BriefParseResult(BaseModel):
    complete: bool
    brief: BriefSchema | None = None
    missing_fields: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None


# --- Conversations ---


class ConversationCreate(BaseModel):
    brand_id: str | None = None


class ConversationResponse(BaseModel):
    id: str
    brand_id: str | None
    created_at: datetime


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime


# --- Jobs / Queue ---


class JobResponse(BaseModel):
    id: str
    conversation_id: str
    brand_id: str
    status: str
    attempts: int
    compliance_score: float | None
    compliance_notes: str | None
    operator_notes: str | None
    output_path: str | None
    created_at: datetime
    updated_at: datetime


class JobRejectRequest(BaseModel):
    notes: str


# --- Brands ---


class BrandCreate(BaseModel):
    name: str
    summary_path: str | None = None
    assets_path: str | None = None


class BrandOnboardSchema(BaseModel):
    """Brand info extracted from conversational onboarding."""

    name: str
    tagline: str | None = None
    summary: str
    colours: list[dict] = Field(default_factory=list)  # [{"name": "Primary", "hex": "#2C1810"}]
    typography: str | None = None
    tone: str | None = None
    target_audience: str | None = None
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)


class BrandResponse(BaseModel):
    id: str
    name: str
    summary_path: str | None
    assets_path: str | None
    created_at: datetime


# --- Health ---


class HealthResponse(BaseModel):
    ollama: str
    chromadb: str
    comfyui: str
    database: str
