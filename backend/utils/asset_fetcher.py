"""Asset fetcher — downloads and validates asset links from briefs.

Each link is checked for accessibility, downloaded with size/timeout
limits, then validated for format and dimensions. Platform-specific
error messages help the user fix common sharing issues.
"""

import mimetypes
from pathlib import Path

import httpx
from PIL import Image

from backend.config import settings
from backend.schemas import AssetResult

# Platform-specific error messages per TDD section 9.
_PLATFORM_ERRORS: dict[str, dict[int, str]] = {
    "drive.google.com": {
        403: (
            "This Google Drive link is restricted. Please change sharing "
            "to 'Anyone with the link can view'"
        ),
    },
    "dropbox.com": {
        404: "This Dropbox link has expired. Please generate a new shared link",
    },
    "wetransfer.com": {
        410: "This WeTransfer link has expired. Please re-upload and share a new link",
    },
}

# Minimum dimensions for asset validation per PRD section 6.
_MIN_LOGO_PX = 500
_MIN_HERO_SHORT_SIDE_PX = 1080

_MAX_DOWNLOAD_BYTES = settings.max_asset_download_size_mb * 1024 * 1024
_TIMEOUT_S = settings.asset_download_timeout_s


async def fetch_asset(url: str, expected_type: str) -> AssetResult:
    """Download a single asset URL and validate it.

    Two-phase approach: HEAD request to check accessibility without
    downloading, then GET to fetch the actual file. This catches
    permission errors before wasting bandwidth.
    """
    result = AssetResult(url=url, identified_type=expected_type)

    # Convert Google Drive sharing links to direct download URLs
    url = _convert_gdrive_url(url)

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=httpx.Timeout(_TIMEOUT_S)
    ) as client:
        # Phase 1: check accessibility
        try:
            head_resp = await client.head(url, timeout=10.0)
        except httpx.TimeoutException:
            result.issues.append("Link timed out")
            result.advice = (
                "This link timed out. Please check it is publicly "
                "accessible and try again"
            )
            return result
        except httpx.RequestError as exc:
            result.issues.append(f"Cannot reach URL: {exc}")
            result.advice = "This link could not be reached. Please check the URL"
            return result

        if head_resp.status_code >= 400:
            _apply_platform_error(url, head_resp.status_code, result)
            return result

        # Phase 2: download the file
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.TimeoutException:
            result.issues.append("Download timed out after 30s")
            result.advice = (
                "File download timed out. Please ensure the file is under "
                f"{settings.max_asset_download_size_mb}MB and publicly accessible"
            )
            return result
        except httpx.HTTPStatusError as exc:
            _apply_platform_error(url, exc.response.status_code, result)
            return result

        if len(resp.content) > _MAX_DOWNLOAD_BYTES:
            result.issues.append(
                f"File exceeds {settings.max_asset_download_size_mb}MB limit"
            )
            result.classification = "BLOCKER"
            result.advice = (
                f"This file is too large. Maximum size is "
                f"{settings.max_asset_download_size_mb}MB"
            )
            return result

        # Save to temp directory — use Content-Disposition filename if available
        cd_filename = ""
        cd = resp.headers.get("content-disposition", "")
        if "filename=" in cd:
            cd_filename = cd.split("filename=")[-1].strip('"').strip("'")
        local_path = _save_to_temp(url, resp.content, cd_filename)
        result.local_path = str(local_path)

        # Identify format from content, not filename (per Ray's spec)
        result.format = _identify_format(local_path, resp.content)

        # Validate based on expected type
        if expected_type == "font":
            _validate_font(local_path, result)
        elif result.format in ("png", "jpg", "jpeg", "svg"):
            _validate_image(local_path, expected_type, result)
        else:
            result.issues.append(f"Unexpected file format: {result.format}")
            result.classification = "WARNING"

    return result


def _apply_platform_error(url: str, status_code: int, result: AssetResult) -> None:
    """Map HTTP errors to user-friendly platform-specific messages.

    Google Drive 403, Dropbox 404, WeTransfer 410 are the most common
    sharing failures — each gets a specific fix instruction.
    """
    result.classification = "BLOCKER"
    for domain, errors in _PLATFORM_ERRORS.items():
        if domain in url and status_code in errors:
            result.issues.append(errors[status_code])
            result.advice = errors[status_code]
            return

    result.issues.append(f"HTTP {status_code} error accessing link")
    result.advice = (
        f"This link returned an error ({status_code}). "
        "Please check it is publicly accessible and try again"
    )


def _save_to_temp(url: str, content: bytes, cd_filename: str = "") -> Path:
    """Write downloaded bytes to a temp file.

    Uses Content-Disposition filename if available (e.g. from Google Drive),
    falls back to URL path, then hash.
    """
    temp_dir = settings.temp_dir
    temp_dir.mkdir(parents=True, exist_ok=True)

    if cd_filename and len(cd_filename) <= 100:
        filename = cd_filename
    else:
        url_path = url.split("?")[0].split("/")[-1]
        if not url_path or len(url_path) > 100 or url_path in ("uc", "download"):
            filename = f"asset_{hash(url) % 10**8}"
        else:
            filename = url_path

    local_path = temp_dir / filename
    local_path.write_bytes(content)
    return local_path


def _identify_format(path: Path, content: bytes) -> str:
    """Detect file format from magic bytes, not filename extension.

    Filenames lie — a .png might actually be a JPEG. Magic bytes are
    the source of truth for image formats.
    """
    # Check magic bytes for common image formats
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:2] == b"\xff\xd8":
        return "jpg"
    if content[:4] == b"<svg" or b"<svg" in content[:200]:
        return "svg"
    if content[:5] == b"%PDF-":
        return "pdf"
    if content[:4] in (b"\x00\x01\x00\x00", b"OTTO"):
        return "otf"
    if content[:4] == b"\x00\x01\x00\x00":
        return "ttf"

    # Fall back to mimetypes from extension
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime.split("/")[-1]

    return "unknown"


def _validate_image(
    path: Path, expected_type: str, result: AssetResult
) -> None:
    """Check image dimensions and transparency per PRD section 6.

    Logo validation is stricter (500px min, transparency required).
    Hero images need 1080px on the shortest side.
    """
    if result.format == "svg":
        # SVG validation is minimal — we trust vector files
        result.usable = True
        result.classification = "OK"
        return

    try:
        with Image.open(path) as img:
            result.dimensions = img.size
            result.has_transparency = img.mode in ("RGBA", "LA", "PA")
            w, h = img.size

            if expected_type == "logo":
                if w < _MIN_LOGO_PX or h < _MIN_LOGO_PX:
                    result.issues.append(
                        f"Logo is {w}x{h}px — minimum is "
                        f"{_MIN_LOGO_PX}x{_MIN_LOGO_PX}px"
                    )
                    result.classification = "BLOCKER"
                    result.advice = (
                        "Please provide SVG or high-res PNG with transparent "
                        f"background, min {_MIN_LOGO_PX}x{_MIN_LOGO_PX}px"
                    )
                    return

                if not result.has_transparency:
                    result.issues.append("Logo has no transparent background")
                    result.classification = "BLOCKER"
                    result.advice = (
                        "Please provide a logo with a transparent background "
                        "(PNG with alpha channel or SVG)"
                    )
                    return

            elif expected_type == "hero":
                short_side = min(w, h)
                if short_side < _MIN_HERO_SHORT_SIDE_PX:
                    result.issues.append(
                        f"Hero image shortest side is {short_side}px — "
                        f"recommend minimum {_MIN_HERO_SHORT_SIDE_PX}px"
                    )
                    result.classification = "WARNING"
                    result.advice = (
                        "Image may appear low quality. Proceeding but "
                        "recommend higher resolution"
                    )
                    # WARNING, not BLOCKER — still usable
                    result.usable = True
                    return

            result.usable = True
            result.classification = "OK"

    except Exception as exc:
        result.issues.append(f"Cannot open image: {exc}")
        result.classification = "WARNING"
        result.advice = "Could not read this file. Proceeding without it"


def _validate_font(path: Path, result: AssetResult) -> None:
    """Check that a font file can be loaded.

    Cairo font loading is tested at composition time — here we just
    check the file is a recognised font format. Non-font files get
    a WARNING (not BLOCKER) so the pipeline can fall back to DejaVuSans.
    """
    if result.format in ("otf", "ttf"):
        result.usable = True
        result.classification = "OK"
    else:
        result.issues.append(f"Expected font file (OTF/TTF), got {result.format}")
        result.classification = "WARNING"
        result.usable = False
        result.advice = (
            "Could not use this as a font file. "
            "Will use a fallback system font instead"
        )


def _convert_gdrive_url(url: str) -> str:
    """Convert Google Drive sharing URLs to direct download links.

    /file/d/FILE_ID/view?... → /uc?export=download&id=FILE_ID
    """
    import re

    match = re.match(
        r"https?://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", url
    )
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url
