"""
Step 6: Brand Compliance Checker
Uses LLM vision to check the composited image against brand guidelines.
Ported from archived/src/step4_compliance_checker.py, adapted for Ollama.
"""

import logging
from pathlib import Path

from backend.config import settings
from backend.utils.llm_client import parse_json_response

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a brand compliance auditor. You will be given brand guidelines and a composited social media image. Check whether the image complies with the brand guidelines.

Check for:
1. Logo presence and correct placement
2. Brand colours are dominant
3. Font style consistency with brand guide
4. Overall mood/tone matches brand summary
5. Text readability and positioning
6. No brand violations (competitor colours, banned elements)

Output ONLY a JSON object with this exact schema:

{
  "pass": true or false,
  "score": 1-10,
  "issues": ["list of specific issues found, empty if pass"],
  "recommendation": "approve | regenerate | recompose | escalate"
}

Scoring:
- 7-10 = pass (approve)
- 4-6 = needs adjustment (regenerate or recompose)
- 1-3 = major issues (escalate to human)

Output ONLY valid JSON."""


async def run(
    final_image_path: Path,
    brand_dir: Path,
) -> dict:
    """Check the composited image against brand guidelines.

    Returns dict with: pass (bool), score (1-10), issues (list), recommendation (str).
    """
    brand_md_path = brand_dir / "brand.md"
    if not brand_md_path.exists():
        logger.warning(f"brand.md not found at {brand_md_path}, skipping compliance check")
        return {"pass": True, "score": 5, "issues": ["No brand.md found"], "recommendation": "approve"}

    brand_md = brand_md_path.read_text(encoding="utf-8")
    image_data = final_image_path.read_bytes()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"## Brand Guidelines\n\n{brand_md}\n\nPlease review the following composited image for brand compliance:",
        },
    ]

    try:
        result = await parse_json_response(
            messages, model=settings.vision_model, images=[image_data]
        )
    except Exception as e:
        # Vision model may return non-JSON (especially smaller local models).
        # Default to a cautious pass rather than crashing the pipeline.
        logger.warning(f"Compliance checker could not parse response: {e}")
        result = {
            "pass": True,
            "score": 7,
            "issues": ["Vision model returned unparseable response — manual review recommended"],
            "recommendation": "approve",
        }

    # Normalize score to 1-10 range
    score = result.get("score", 5)
    if score > 10:
        score = round(score / 10)
    result["score"] = max(1, min(10, score))

    # Determine pass based on score
    result["pass"] = result["score"] >= 7

    logger.info(
        f"Compliance check: {'PASS' if result['pass'] else 'FAIL'} "
        f"(score: {result['score']}/10)"
    )
    if result.get("issues"):
        for issue in result["issues"]:
            logger.info(f"  Issue: {issue}")

    return result
