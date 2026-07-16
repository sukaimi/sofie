"""Pexels stock photo search — real-photo hero source.

Sits between the client-provided hero and Flux generation in the hero
priority order: a real stock photo beats a generated one for brand quality
and is free. Every failure mode (no key, 401, 429, timeout, zero results)
returns an empty list so the caller can fall through to generation — a
stock miss must NEVER fail the job.

Per CLAUDE.md: text is never rendered here — Pexels supplies the base
photograph only; all copy is applied later by Cairo + Pango.
"""

from dataclasses import dataclass

import httpx

from backend.config import settings

_SEARCH_URL = "https://api.pexels.com/v1/search"
_TIMEOUT_S = 15.0


@dataclass
class PexelsPhoto:
    """A single usable Pexels photo candidate.

    Mirrors the fields SOFIE needs from the Pexels photo resource:
    download URLs, real dimensions, and photographer attribution.
    """

    id: int
    width: int
    height: int
    src_original: str
    src_large2x: str
    photographer: str
    photographer_url: str
    alt: str


async def search_photos(
    query: str,
    orientation: str,
    per_page: int,
    min_width: int,
) -> list[PexelsPhoto]:
    """Search Pexels photos. Returns usable candidates sorted by resolution.

    Empty list on no results, missing key, auth failure, rate limit, or
    timeout — the caller falls back to generation. Candidates below
    ``min_width`` are filtered out; the widest photo comes first so the
    highest-resolution match is tried before lower-quality ones.

    ``orientation`` must be one of "landscape", "portrait", or "square".
    """
    if not settings.pexels_api_key:
        return []

    params: dict[str, str | int] = {
        "query": query,
        "per_page": per_page,
        "size": "large",
    }
    if orientation in ("landscape", "portrait", "square"):
        params["orientation"] = orientation

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            # Pexels auth: raw key in the Authorization header, no "Bearer" prefix.
            resp = await client.get(
                _SEARCH_URL,
                params=params,
                headers={"Authorization": settings.pexels_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        import logging

        logging.getLogger("sofie.pexels").warning(f"Pexels search failed: {exc}")
        return []

    photos: list[PexelsPhoto] = []
    for item in data.get("photos", []):
        src = item.get("src", {}) or {}
        width = int(item.get("width", 0) or 0)
        if width < min_width:
            continue
        photos.append(
            PexelsPhoto(
                id=int(item.get("id", 0) or 0),
                width=width,
                height=int(item.get("height", 0) or 0),
                src_original=src.get("original", ""),
                src_large2x=src.get("large2x", ""),
                photographer=item.get("photographer", ""),
                photographer_url=item.get("photographer_url", ""),
                alt=item.get("alt", "") or "",
            )
        )

    # Highest resolution first — try the best candidate before lesser ones.
    photos.sort(key=lambda p: p.width, reverse=True)
    return photos
