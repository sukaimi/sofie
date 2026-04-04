"""
Step 3: Prompt Engineer
Generates an image generation prompt from the brief + brand context.
Ported from archived step1_prompt_engineer.py, adapted for Ollama.
"""

import logging
from pathlib import Path

from backend.schemas import BriefSchema
from backend.utils.llm_client import parse_json_response

logger = logging.getLogger(__name__)


def audit_assets(brand_dir: Path) -> dict:
    """Scan the brand's /assets folder and list what's available.

    Ported from archived/src/step1_prompt_engineer.py.
    """
    assets: dict = {
        "logo": None,
        "fonts": [],
        "images": [],
        "elements": [],
        "references": [],
    }

    assets_dir = brand_dir / "assets"
    if not assets_dir.exists():
        return assets

    # Logo
    for ext in ("svg", "png"):
        logo = assets_dir / f"logo.{ext}"
        if logo.exists():
            assets["logo"] = logo.name
            break

    # Fonts
    fonts_dir = assets_dir / "fonts"
    if fonts_dir.exists():
        assets["fonts"] = [
            f.name
            for f in fonts_dir.iterdir()
            if f.suffix.lower() in (".otf", ".ttf")
        ]
    for f in assets_dir.iterdir():
        if f.suffix.lower() in (".otf", ".ttf") and f.name not in assets["fonts"]:
            assets["fonts"].append(f.name)

    # Images
    images_dir = assets_dir / "images"
    if images_dir.exists():
        assets["images"] = [
            f.name
            for f in images_dir.iterdir()
            if f.suffix.lower() in (".jpg", ".jpeg", ".png")
        ]

    # Elements
    elements_dir = assets_dir / "elements"
    if elements_dir.exists():
        assets["elements"] = [
            f.name
            for f in elements_dir.iterdir()
            if f.suffix.lower() in (".svg", ".png")
        ]

    # References
    refs_dir = assets_dir / "references"
    if refs_dir.exists():
        assets["references"] = [
            f.name
            for f in refs_dir.iterdir()
            if f.suffix.lower() in (".jpg", ".jpeg", ".png")
        ]

    return assets


SYSTEM_PROMPT = """You are a senior creative director at a social media agency. Generate a detailed image generation prompt for Flux.1 Schnell based on a creative brief and brand context.

Output ONLY a JSON object with this schema:

{
  "image_prompt": "Detailed image generation prompt describing the visual scene, composition, lighting, and mood. DO NOT include any text rendering instructions — all text is applied separately by the compositor.",
  "hero_image": "filename from available assets or null",
  "elements": ["element filenames to use"],
  "logo": "logo filename",
  "font": "font filename or null",
  "headline_text": "headline copy from brief",
  "sub_copy": "sub-copy text or null",
  "cta": "call to action text or null",
  "logo_placement": "top-left | top-right | bottom-left | bottom-right | bottom-centre | top-centre",
  "headline_placement": "top | centre | bottom",
  "output_dimensions": "WIDTHxHEIGHT",
  "colour_overlay": "#HEXCODE at N% opacity or null"
}

CRITICAL RULES:
- The image_prompt must NEVER contain text rendering instructions (no "text saying...", no "words that read...", no "title: ...")
- The image_prompt should describe only the visual scene, composition, colours, lighting, mood, and subject matter
- Reference the brand colour palette in the image_prompt
- Match the tone described in the brief
- Use available assets where possible

Output ONLY valid JSON."""


async def run(
    brief: BriefSchema,
    brand_context: str,
    brand_dir: Path,
    compliance_notes: str | None = None,
) -> dict:
    """Generate a prompt package from brief + brand context.

    Args:
        brief: The structured brief.
        brand_context: RAG-retrieved brand context from ChromaDB.
        brand_dir: Path to the brand's directory.
        compliance_notes: Optional notes from a failed compliance check for retry.

    Returns:
        Prompt package dict for image generation and compositing.
    """
    import json

    assets = audit_assets(brand_dir)

    user_content = f"""## Brand Context
{brand_context}

## Creative Brief
- Platform: {brief.platform}
- Dimensions: {brief.dimensions}
- Campaign: {brief.campaign or 'Not specified'}
- Key Message: {brief.key_message or 'Not specified'}
- Tone: {brief.tone or 'Not specified'}
- Must Include: {', '.join(brief.must_include) if brief.must_include else 'None'}
- Must Avoid: {', '.join(brief.must_avoid) if brief.must_avoid else 'None'}
- Text Overlays: {json.dumps([t.model_dump() for t in brief.text_overlays]) if brief.text_overlays else 'None specified'}

## Available Assets
{json.dumps(assets, indent=2)}"""

    if compliance_notes:
        user_content += f"\n\n## Previous Compliance Feedback (fix these issues)\n{compliance_notes}"

    user_content += "\n\nGenerate the prompt package JSON now."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    prompt_package = await parse_json_response(messages)

    # Ensure dimensions match brief
    prompt_package["output_dimensions"] = brief.dimensions

    # Extract text overlays from brief if not in prompt package
    if brief.text_overlays:
        if not prompt_package.get("headline_text"):
            for overlay in brief.text_overlays:
                if overlay.style == "headline":
                    prompt_package["headline_text"] = overlay.text
                elif overlay.style == "subhead":
                    prompt_package["sub_copy"] = overlay.text
                elif overlay.style == "cta":
                    prompt_package["cta"] = overlay.text

    logger.info(f"Generated prompt package for {brief.brand}/{brief.campaign}")
    return prompt_package
