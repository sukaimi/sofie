"""Download link generation for approved output files.

Generates file-specific download URLs. Output directory is not publicly
browsable — only specific file links work. Files are served by FastAPI's
FileResponse.
"""

from pathlib import Path

from backend.config import settings


def generate_download_url(job_id: str, filename: str) -> str:
    """Create a download URL for a specific output file.

    URL format: {base_url}/job/{job_id}/download/{filename}
    The corresponding route in main.py validates the path exists
    before serving.
    """
    base = settings.file_server_base_url.rstrip("/")
    return f"{base}/job/{job_id}/download/{filename}"


def get_output_path(job_id: str, size: str, fmt: str = "") -> Path:
    """Build the filesystem path for a composited output file.

    Convention: output/{job_id}/composited_{size}.{ext}
    This matches the pattern Kai uses when saving.
    """
    ext = fmt.lower() or settings.default_output_format.lower()
    if ext == "jpg":
        ext = "jpg"
    filename = f"composited_{size}.{ext}"
    return settings.output_dir / job_id / filename


def list_output_files(job_id: str) -> list[dict[str, str]]:
    """List all output files for a job with their download URLs.

    Used by Sofie to build the delivery message and by the operator
    dashboard to show preview links.
    """
    job_dir = settings.output_dir / job_id
    if not job_dir.exists():
        return []

    files = []
    for path in sorted(job_dir.glob("composited_*")):
        files.append(
            {
                "filename": path.name,
                "path": str(path),
                "url": generate_download_url(job_id, path.name),
                "size_bytes": path.stat().st_size,
            }
        )

    return files
