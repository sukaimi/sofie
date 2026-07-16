"""Base image generation — last-resort hero source.

Triggered ONLY when neither a client hero image nor a Pexels stock photo
is available. Providers are tried in order — primary then fallback — and
every one fails gracefully (returns None) so the pipeline degrades safely:

  - google:       Gemini "Nano Banana" via AI Studio (free tier, needs key)
  - pollinations: Pollinations.ai (free, no API key)
  - replicate:    Flux.1 Dev via Replicate (paid)

Per CLAUDE.md: prompts must NOT contain text rendering instructions — all
text is applied post-generation by Cairo + Pango.
"""

import base64
import logging
from pathlib import Path
from urllib.parse import quote

import httpx

from backend.config import settings

log = logging.getLogger("sofie.image_gen")

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
_POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"


async def generate_image(
    prompt: str,
    dimensions: tuple[int, int],
    job_id: str,
) -> Path | None:
    """Generate a base hero image, trying providers in priority order.

    Runs the configured primary provider, then the fallback, returning
    the local path of the first success. Returns None if generation is
    disabled or every provider fails — the pipeline can proceed without
    a hero if the user acknowledges.
    """
    if settings.image_gen_disabled:
        return None

    width, height = dimensions

    # Strip any text instructions from the prompt — per design rules,
    # text is NEVER rendered by the image generation model.
    clean_prompt = _strip_text_instructions(prompt)

    # Ordered, de-duplicated provider chain: primary then fallback.
    providers: list[str] = []
    for name in (settings.image_gen_provider, settings.image_gen_fallback):
        if name and name != "none" and name not in providers:
            providers.append(name)

    out_dir = settings.output_dir / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    _handlers = {
        "google": _gen_google,
        "pollinations": _gen_pollinations,
        "replicate": _gen_replicate,
    }

    for provider in providers:
        handler = _handlers.get(provider)
        if not handler:
            continue
        try:
            path = await handler(clean_prompt, width, height, out_dir)
        except Exception as exc:
            log.warning(f"Image provider '{provider}' failed: {exc}")
            path = None
        if path:
            log.info(f"Hero image generated via '{provider}'")
            return path

    return None


async def _gen_google(
    prompt: str, width: int, height: int, out_dir: Path
) -> Path | None:
    """Generate via Gemini "Nano Banana" (Google AI Studio, free tier).

    The docs disagree on the aspect-ratio field name between REST
    (responseFormat.image) and the SDK (imageConfig), so we try both
    then fall back to a minimal request — Google generation still works
    even if only the default aspect ratio is honoured.
    """
    if not settings.google_ai_api_key:
        return None

    url = _GEMINI_URL.format(model=settings.nano_banana_model)
    headers = {
        "x-goog-api-key": settings.google_ai_api_key,
        "Content-Type": "application/json",
    }

    image_cfg: dict[str, str] = {"aspectRatio": _aspect_ratio(width, height)}
    if settings.gemini_image_size:
        image_cfg["imageSize"] = settings.gemini_image_size

    contents = [{"parts": [{"text": prompt}]}]
    # imageConfig is what gemini-2.5-flash-image actually accepts (confirmed by a
    # live call — the REST docs' responseFormat.image shape returns 400). We try
    # imageConfig first, then responseFormat.image (in case another model wants
    # it), then a minimal request so generation still works with no aspect control.
    candidate_configs = [
        {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": image_cfg},
        {"responseModalities": ["TEXT", "IMAGE"], "responseFormat": {"image": image_cfg}},
        {"responseModalities": ["TEXT", "IMAGE"]},
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = None
        for gen_config in candidate_configs:
            resp = await client.post(
                url,
                headers=headers,
                json={"contents": contents, "generationConfig": gen_config},
            )
            # A 400 usually means this generationConfig shape was rejected —
            # try the next candidate before giving up.
            if resp.status_code != 400:
                break
        resp.raise_for_status()
        data = resp.json()

    img_bytes = _extract_gemini_image(data)
    if not img_bytes:
        return None

    path = out_dir / "generated_hero.png"
    path.write_bytes(img_bytes)
    return path


def _extract_gemini_image(data: dict) -> bytes | None:
    """Pull the first inline image out of a generateContent response.

    Handles both camelCase (REST) and snake_case (SDK-shaped) keys.
    """
    for candidate in data.get("candidates", []):
        parts = (candidate.get("content") or {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                try:
                    return base64.b64decode(inline["data"])
                except (ValueError, TypeError):
                    continue
    return None


async def _gen_pollinations(
    prompt: str, width: int, height: int, out_dir: Path
) -> Path | None:
    """Generate via Pollinations.ai — free, no API key required."""
    url = _POLLINATIONS_URL.format(prompt=quote(prompt))
    params = {"width": width, "height": height, "nologo": "true"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        content = resp.content

    if not content or not resp.headers.get("content-type", "").startswith("image"):
        return None

    path = out_dir / "generated_hero.jpg"
    path.write_bytes(content)
    return path


async def _gen_replicate(
    prompt: str, width: int, height: int, out_dir: Path
) -> Path | None:
    """Generate via Flux.1 Dev on Replicate (paid — last resort)."""
    if not settings.replicate_api_key:
        return None

    output_url = await _call_replicate(prompt, width, height)
    if not output_url:
        return None

    path = out_dir / "generated_hero.png"
    async with httpx.AsyncClient() as client:
        resp = await client.get(output_url, timeout=60.0)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def _aspect_ratio(width: int, height: int) -> str:
    """Map pixel dimensions to the nearest Nano Banana aspect-ratio string."""
    if height == 0:
        return "1:1"
    ratio = width / height
    if ratio > 1.05:
        return "16:9"
    if ratio < 0.95:
        return "4:5"
    return "1:1"


async def _call_replicate(prompt: str, width: int, height: int) -> str | None:
    """Call the Replicate API to run Flux.1 Dev.

    Uses the predictions API for async generation. Polls until
    the prediction completes or fails.
    """
    import replicate

    client = replicate.Client(api_token=settings.replicate_api_key)

    output = client.run(
        settings.flux_model,
        input={
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_outputs": 1,
            "guidance_scale": 3.5,
            "num_inference_steps": 28,
        },
    )

    # Replicate returns a list of URLs
    if output and isinstance(output, list) and len(output) > 0:
        return str(output[0])

    return None


def _strip_text_instructions(prompt: str) -> str:
    """Remove any text/typography instructions from the prompt.

    Image generation models hallucinate text badly. All text in SOFIE
    compositions is rendered by Cairo + Pango post-generation.
    """
    # Common text-related phrases to strip
    text_patterns = [
        "with text",
        "with the text",
        "text saying",
        "text reads",
        "text that says",
        "with typography",
        "with lettering",
        "with words",
        "with the word",
        "include text",
        "add text",
        "write text",
        "showing text",
    ]

    result = prompt
    for pattern in text_patterns:
        lower = result.lower()
        idx = lower.find(pattern)
        if idx >= 0:
            # Remove from the pattern to the next period or end of string
            end = result.find(".", idx)
            if end >= 0:
                result = result[:idx] + result[end + 1:]
            else:
                result = result[:idx]

    return result.strip()
