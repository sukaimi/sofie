"""Flux.1 Dev image generation via Replicate API — fallback only.

Triggered ONLY when no hero image is provided by the client.
Per CLAUDE.md: prompts must NOT contain text rendering instructions.
All text is applied post-generation by Cairo + Pango.
"""

from pathlib import Path

import httpx

from backend.config import settings


async def generate_image(
    prompt: str,
    dimensions: tuple[int, int],
    job_id: str,
) -> Path | None:
    """Generate a base image using Flux.1 Dev via Replicate.

    Returns the local path to the generated image, or None if
    generation is disabled or fails. The pipeline treats this as
    a graceful fallback — jobs can proceed without hero images
    if the user acknowledges.
    """
    if settings.image_gen_disabled:
        return None

    if not settings.replicate_api_key:
        return None

    width, height = dimensions

    # Strip any text instructions from the prompt — per design rules,
    # text is NEVER rendered by the image generation model.
    clean_prompt = _strip_text_instructions(prompt)

    try:
        output_url = await _call_replicate(clean_prompt, width, height)
        if not output_url:
            return None

        # Download the generated image
        local_path = settings.output_dir / job_id / "generated_hero.png"
        local_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient() as client:
            resp = await client.get(output_url, timeout=60.0)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)

        return local_path

    except Exception:
        return None


async def _call_replicate(
    prompt: str, width: int, height: int
) -> str | None:
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
