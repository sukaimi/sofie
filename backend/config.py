from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"
    vision_model: str = "llama3.2-vision:latest"

    # ComfyUI / Flux API
    comfyui_base_url: str = "http://localhost:8188"
    comfyui_mock: bool = True
    flux_api_key: str = ""
    flux_api_provider: str = ""  # replicate | fal | bfl

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sofie.db"

    # Fallback
    google_ai_studio_key: str = ""

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    brands_dir: Path = base_dir / "brands"
    output_dir: Path = base_dir / "output"
    data_dir: Path = base_dir / "data"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
