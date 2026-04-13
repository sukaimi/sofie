"""Pydantic schemas for API request/response validation.

Kept separate from SQLAlchemy models so the API layer stays decoupled
from the persistence layer.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check endpoint response."""

    status: str = "ok"
    version: str = "0.1.0"


class JobStatusResponse(BaseModel):
    """Lightweight job status for polling."""

    job_id: str
    status: str
    brand_name: str
    job_title: str
    total_cost_usd: float
    compliance_attempts: int
    user_revision_count: int


class AssetResult(BaseModel):
    """Result of fetching and validating a single asset link.

    Each asset is classified independently so the pipeline can proceed
    with valid assets while reporting issues on others.
    """

    url: str
    local_path: str | None = None
    identified_type: str = "unknown"
    format: str = ""
    dimensions: tuple[int, int] | None = None
    has_transparency: bool | None = None
    usable: bool = False
    issues: list[str] = Field(default_factory=list)
    classification: str = "BLOCKER"
    advice: str | None = None


class BriefField(BaseModel):
    """A single extracted field from the .docx brief."""

    name: str
    value: str | None = None
    classification: str = "OPTIONAL"


class BriefParseResult(BaseModel):
    """Structured output from brief parsing.

    Includes both the extracted fields and any warnings about content
    that could not be extracted (e.g. text boxes, embedded objects).
    """

    fields: dict[str, str | list[str] | None]
    warnings: list[str] = Field(default_factory=list)
    has_text_boxes: bool = False


class WebSocketMessage(BaseModel):
    """Standard WebSocket message envelope per TDD section 14."""

    type: str  # message | status | image | error | action_required
    role: str  # sofie | user | system
    content: str
    job_id: str | None = None
    metadata: dict = Field(default_factory=dict)
