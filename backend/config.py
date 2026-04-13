"""Application settings loaded from .env via pydantic-settings.

Centralises all configuration so no module reads os.environ directly.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All SOFIE configuration — mapped 1:1 from .env variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── API Keys ──────────────────────────────────────────────
    anthropic_api_key: str = ""
    replicate_api_key: str = ""
    google_ai_api_key: str = ""

    # ── LLM Models ────────────────────────────────────────────
    llm_model_opus: str = "claude-opus-4-6"
    llm_model_sonnet: str = "claude-sonnet-4-6"
    llm_model_haiku: str = "claude-haiku-4-5-20251001"

    # ── Image Generation ──────────────────────────────────────
    image_gen_provider: str = "replicate"
    flux_model: str = "black-forest-labs/flux-dev"
    nano_banana_model: str = "gemini-3-pro-image-preview"
    image_gen_disabled: bool = False

    # ── Pipeline Limits ───────────────────────────────────────
    cost_ceiling_usd: float = 2.00
    max_qa_attempts: int = 3
    max_user_revisions: int = 2
    max_asset_resubmissions: int = 3
    max_brief_resubmissions: int = 3
    max_clarification_exchanges: int = 3

    # ── File Handling ─────────────────────────────────────────
    max_upload_size_mb: int = 50
    max_asset_download_size_mb: int = 50
    asset_download_timeout_s: int = 30
    default_output_format: str = "JPG"
    jpg_quality: int = 92

    # ── Database ──────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/sofie.db"

    # ── Redis + Celery ────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # ── Server ────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    frontend_url: str = "http://localhost:3000"
    file_server_base_url: str = "http://localhost:8000/files"

    # ── Paths ─────────────────────────────────────────────────
    brands_dir: Path = Path("/app/brands")
    brief_template_path: Path = Path("/app/briefs/brief-template.docx")
    output_dir: Path = Path("/app/output")
    temp_dir: Path = Path("/tmp/sofie")


settings = Settings()
