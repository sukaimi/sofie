"""
Step 4: Image Generator
Generates the raw base image via ComfyUI (or mock).
"""

import logging
from pathlib import Path

from backend.utils.comfyui_client import generate_image

logger = logging.getLogger(__name__)


async def run(prompt_package: dict, job_id: str) -> Path:
    """Generate the raw base image.

    Args:
        prompt_package: The prompt package from the prompt engineer step.
        job_id: Unique job ID for output directory.

    Returns:
        Path to the raw generated image.
    """
    image_prompt = prompt_package.get("image_prompt", "")
    dimensions = prompt_package.get("output_dimensions", "1080x1080")

    logger.info(f"Generating image for job {job_id} ({dimensions})")
    raw_path = await generate_image(image_prompt, dimensions, job_id)
    logger.info(f"Raw image saved: {raw_path}")

    return raw_path
