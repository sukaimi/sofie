import json
import logging
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from backend.config import settings

logger = logging.getLogger(__name__)


def _parse_dimensions(dimensions: str) -> tuple[int, int]:
    """Parse 'WIDTHxHEIGHT' string into (width, height) tuple."""
    parts = dimensions.lower().split("x")
    return int(parts[0]), int(parts[1])


async def generate_image(
    prompt: str,
    dimensions: str,
    job_id: str,
) -> Path:
    """Generate an image via Flux API, ComfyUI, or mock.

    Priority:
    1. If FLUX_API_KEY is set → use external Flux API (Replicate/fal/BFL)
    2. If COMFYUI_MOCK=false → use self-hosted ComfyUI
    3. Otherwise → generate Pillow placeholder (mock)

    Returns path to the raw generated image.
    """
    output_dir = settings.output_dir / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "raw.png"

    if settings.flux_api_key:
        return await _generate_flux_api(prompt, dimensions, output_path)
    elif not settings.comfyui_mock:
        return await _generate_comfyui(prompt, dimensions, output_path)
    else:
        return _generate_mock(prompt, dimensions, output_path)


def _generate_mock(prompt: str, dimensions: str, output_path: Path) -> Path:
    """Generate a placeholder image using Pillow."""
    width, height = _parse_dimensions(dimensions)

    # Warm background matching the creative tool vibe
    img = Image.new("RGB", (width, height), color=(45, 42, 46))
    draw = ImageDraw.Draw(img)

    # Try to use a decent font, fall back to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    # Draw mock label
    label = "MOCK IMAGE"
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(
        ((width - text_w) // 2, height // 3),
        label,
        fill=(212, 165, 116),
        font=font,
    )

    # Draw truncated prompt
    truncated = prompt[:80] + "..." if len(prompt) > 80 else prompt
    draw.text(
        (40, height // 2),
        truncated,
        fill=(150, 150, 150),
        font=small_font,
    )

    # Draw dimensions
    dim_text = f"{width}x{height}"
    bbox = draw.textbbox((0, 0), dim_text, font=small_font)
    dim_w = bbox[2] - bbox[0]
    draw.text(
        ((width - dim_w) // 2, height * 2 // 3),
        dim_text,
        fill=(100, 100, 100),
        font=small_font,
    )

    img.save(output_path, "PNG")
    logger.info(f"Mock image generated: {output_path}")
    return output_path


async def _generate_flux_api(
    prompt: str, dimensions: str, output_path: Path
) -> Path:
    """Generate image via external Flux API."""
    width, height = _parse_dimensions(dimensions)
    provider = settings.flux_api_provider.lower()

    if provider == "openrouter":
        return await _flux_openrouter(prompt, width, height, output_path)
    elif provider == "fal":
        return await _flux_fal(prompt, width, height, output_path)
    elif provider == "replicate":
        return await _flux_replicate(prompt, width, height, output_path)
    elif provider == "bfl":
        return await _flux_bfl(prompt, width, height, output_path)
    else:
        raise ValueError(
            f"Unknown FLUX_API_PROVIDER: '{provider}'. "
            "Set to: openrouter | replicate | fal | bfl"
        )


async def _flux_openrouter(
    prompt: str, width: int, height: int, output_path: Path
) -> Path:
    """Generate via OpenRouter's image generation API (Flux 2 models).

    Uses /api/v1/chat/completions with modalities: ["image"].
    Returns base64-encoded images in response.
    """
    import base64

    # Determine aspect ratio for image_config
    if width == height:
        aspect = "1:1"
    elif width > height:
        aspect = "16:9" if width / height > 1.4 else "4:3"
    else:
        aspect = "9:16" if height / width > 1.4 else "3:4"

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.flux_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "black-forest-labs/flux.2-pro",
                "modalities": ["image"],
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "image_config": {
                    "aspect_ratio": aspect,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract base64 image from response
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {data}")

        message = choices[0].get("message", {})
        images = message.get("images", [])

        if not images:
            raise RuntimeError(
                f"OpenRouter returned no images. Response: {data}"
            )

        # Images are returned as data URLs: data:image/png;base64,...
        image_data = images[0]
        if isinstance(image_data, dict):
            image_url = image_data.get("image_url", {}).get("url", "")
        else:
            image_url = str(image_data)

        if image_url.startswith("data:"):
            # base64 data URL
            _, b64_data = image_url.split(",", 1)
            output_path.write_bytes(base64.b64decode(b64_data))
        elif image_url.startswith("http"):
            # Regular URL — download it
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            output_path.write_bytes(img_resp.content)
        else:
            # Raw base64
            output_path.write_bytes(base64.b64decode(image_url))

        logger.info(f"OpenRouter Flux image generated: {output_path}")
        return output_path


async def _flux_fal(
    prompt: str, width: int, height: int, output_path: Path
) -> Path:
    """Generate via fal.ai Flux Schnell API."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.post(
            "https://fal.run/fal-ai/flux/schnell",
            headers={"Authorization": f"Key {settings.flux_api_key}"},
            json={
                "prompt": prompt,
                "image_size": {"width": width, "height": height},
                "num_inference_steps": 4,
                "num_images": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data["images"][0]["url"]

        img_resp = await client.get(image_url)
        img_resp.raise_for_status()
        output_path.write_bytes(img_resp.content)
        logger.info(f"fal.ai Flux image generated: {output_path}")
        return output_path


async def _flux_replicate(
    prompt: str, width: int, height: int, output_path: Path
) -> Path:
    """Generate via Replicate Flux Schnell API."""
    import asyncio

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
            headers={"Authorization": f"Bearer {settings.flux_api_key}"},
            json={
                "input": {
                    "prompt": prompt,
                    "go_fast": True,
                    "num_outputs": 1,
                    "aspect_ratio": f"{width}:{height}" if width != height else "1:1",
                    "output_format": "png",
                },
            },
        )
        resp.raise_for_status()
        prediction = resp.json()
        prediction_url = prediction["urls"]["get"]

        for _ in range(60):
            await asyncio.sleep(2)
            poll_resp = await client.get(
                prediction_url,
                headers={"Authorization": f"Bearer {settings.flux_api_key}"},
            )
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()

            if poll_data["status"] == "succeeded":
                image_url = poll_data["output"][0]
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                output_path.write_bytes(img_resp.content)
                logger.info(f"Replicate Flux image generated: {output_path}")
                return output_path
            elif poll_data["status"] == "failed":
                raise RuntimeError(f"Replicate failed: {poll_data.get('error')}")

        raise TimeoutError("Replicate Flux generation timed out")


async def _flux_bfl(
    prompt: str, width: int, height: int, output_path: Path
) -> Path:
    """Generate via BFL (Black Forest Labs) direct API."""
    import asyncio

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.post(
            "https://api.bfl.ml/v1/flux-pro-1.1",
            headers={"x-key": settings.flux_api_key},
            json={"prompt": prompt, "width": width, "height": height},
        )
        resp.raise_for_status()
        task_id = resp.json()["id"]

        for _ in range(60):
            await asyncio.sleep(2)
            result_resp = await client.get(
                "https://api.bfl.ml/v1/get_result",
                params={"id": task_id},
                headers={"x-key": settings.flux_api_key},
            )
            result_resp.raise_for_status()
            result = result_resp.json()

            if result["status"] == "Ready":
                image_url = result["result"]["sample"]
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                output_path.write_bytes(img_resp.content)
                logger.info(f"BFL Flux image generated: {output_path}")
                return output_path

        raise TimeoutError("BFL Flux generation timed out")


async def _generate_comfyui(
    prompt: str, dimensions: str, output_path: Path
) -> Path:
    """Generate image via ComfyUI REST API."""
    width, height = _parse_dimensions(dimensions)

    # Load Flux Schnell workflow template
    workflow_path = settings.base_dir / "comfyui" / "workflows" / "flux-schnell-txt2img.json"
    if not workflow_path.exists():
        raise FileNotFoundError(f"ComfyUI workflow not found: {workflow_path}")

    with open(workflow_path) as f:
        workflow = json.load(f)

    # Inject prompt and dimensions into workflow
    # (Workflow node IDs depend on the specific workflow JSON — adjust as needed)
    client_id = str(uuid.uuid4())

    async with httpx.AsyncClient(
        base_url=settings.comfyui_base_url,
        timeout=httpx.Timeout(90.0, connect=10.0),
    ) as client:
        # Queue the prompt
        resp = await client.post(
            "/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        # Poll for completion
        import asyncio

        for _ in range(60):  # 60 second timeout
            await asyncio.sleep(1)
            history_resp = await client.get(f"/history/{prompt_id}")
            history_resp.raise_for_status()
            history = history_resp.json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        image_info = node_output["images"][0]
                        filename = image_info["filename"]
                        subfolder = image_info.get("subfolder", "")

                        # Download the image
                        params = {"filename": filename, "subfolder": subfolder}
                        img_resp = await client.get("/view", params=params)
                        img_resp.raise_for_status()
                        output_path.write_bytes(img_resp.content)
                        logger.info(f"ComfyUI image generated: {output_path}")
                        return output_path

        raise TimeoutError(f"ComfyUI generation timed out for prompt {prompt_id}")


def get_image_gen_mode() -> str:
    """Return the current image generation mode label."""
    if settings.flux_api_key:
        return f"flux-api ({settings.flux_api_provider or 'unknown provider'})"
    elif not settings.comfyui_mock:
        return "comfyui"
    else:
        return "mocked"


async def check_health() -> bool:
    """Check if image generation is available."""
    if settings.flux_api_key:
        return True  # API key set, assume reachable
    if settings.comfyui_mock:
        return True
    try:
        async with httpx.AsyncClient(
            base_url=settings.comfyui_base_url, timeout=5.0
        ) as client:
            resp = await client.get("/system_stats")
            return resp.status_code == 200
    except Exception:
        return False
