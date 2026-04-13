"""SQLAlchemy models for SOFIE.

Three tables track the full lifecycle of a job:
- Job: the core unit of work from brief upload to delivery
- AgentLog: per-agent token/cost audit trail
- Conversation: WebSocket chat state tied to a job
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def _generate_job_id() -> str:
    """12-char hex prefixed with JOB- to match Marcus's ID format."""
    return f"JOB-{uuid.uuid4().hex[:12]}"


def _generate_conv_id() -> str:
    """12-char hex prefixed with CONV- to match Marcus's ID format."""
    return f"CONV-{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp for consistent auditing."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for all SOFIE models."""

    pass


class Job(Base):
    """Tracks a single creative production job from brief to delivery.

    Every pipeline step writes its output here so failed jobs can resume
    from the last successful step rather than starting over.
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(16), primary_key=True, default=_generate_job_id
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    brand_name: Mapped[str] = mapped_column(String(255), default="")
    job_title: Mapped[str] = mapped_column(String(255), default="")
    conversation_id: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(
        String(30), default="pending"
    )
    brief_json: Mapped[dict] = mapped_column(JSON, default=dict)
    asset_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    composition_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    output_sizes: Mapped[list] = mapped_column(JSON, default=list)
    primary_size: Mapped[str] = mapped_column(String(20), default="")
    output_paths: Mapped[dict] = mapped_column(JSON, default=dict)
    qa_results: Mapped[dict] = mapped_column(JSON, default=dict)
    compliance_attempts: Mapped[int] = mapped_column(Integer, default=0)
    user_revision_count: Mapped[int] = mapped_column(Integer, default=0)
    operator_notes: Mapped[str] = mapped_column(Text, default="")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_ceiling_usd: Mapped[float] = mapped_column(Float, default=2.00)
    cost_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    error_log: Mapped[str] = mapped_column(Text, default="")


class AgentLog(Base):
    """Audit log for every LLM call an agent makes.

    Enables per-agent cost attribution and debugging of pipeline failures
    without needing to replay the conversation.
    """

    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(16), index=True)
    agent_name: Mapped[str] = mapped_column(String(30))
    step: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="started")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Conversation(Base):
    """WebSocket chat session tied to a job.

    Stores the full message history so Sofie can maintain context across
    reconnections without relying on client-side state.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=_generate_conv_id
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    job_id: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default=None
    )
    messages: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(30), default="greeting")
