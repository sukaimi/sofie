"""Anthropic API wrapper with per-call cost tracking.

Every LLM call in SOFIE routes through this client so we get consistent
token counting, cost calculation, and ceiling enforcement. No agent
should call the Anthropic SDK directly.
"""

import base64
import time

import anthropic

from backend.config import settings

# Cost per million tokens — from ENV.md cost reference table.
_COST_PER_MTK: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
}

# Model aliases for convenience — agents reference these by shorthand.
MODEL_ALIASES: dict[str, str] = {
    "opus": settings.llm_model_opus,
    "sonnet": settings.llm_model_sonnet,
    "haiku": settings.llm_model_haiku,
}


class CostCeilingBreached(Exception):
    """Raised when a job's cumulative LLM cost exceeds its ceiling.

    The orchestrator catches this to pause the job and alert the operator
    rather than silently continuing to spend.
    """

    def __init__(self, job_id: str, current_cost: float, ceiling: float) -> None:
        self.job_id = job_id
        self.current_cost = current_cost
        self.ceiling = ceiling
        super().__init__(
            f"Job {job_id} cost ${current_cost:.4f} exceeds ceiling ${ceiling:.2f}"
        )


class LLMClient:
    """Wrapper for Anthropic API with cost tracking.

    Handles text and vision requests, calculates per-call cost,
    and returns a structured tuple so callers can log token usage
    without parsing raw API responses.
    """

    def __init__(self) -> None:
        """Initialise the Anthropic client with the configured API key."""
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def resolve_model(self, model: str) -> str:
        """Convert alias ('opus', 'sonnet', 'haiku') to full model ID.

        Agents use shorthand names — this maps them to the actual model
        identifiers configured in .env so we can swap models without
        changing agent code.
        """
        return MODEL_ALIASES.get(model, model)

    async def complete(
        self,
        model: str,
        messages: list[dict],
        system: str,
        max_tokens: int = 2048,
        images: list[bytes] | None = None,
        job_id: str | None = None,
        agent_name: str | None = None,
    ) -> tuple[str, int, int, float]:
        """Make a single LLM call and return response with cost.

        Returns (response_text, input_tokens, output_tokens, cost_usd).
        If images are provided, they're base64-encoded and prepended to
        the last user message as image content blocks.
        """
        resolved_model = self.resolve_model(model)

        # Inject images into the last user message if provided
        if images:
            messages = _inject_images(messages, images)

        start_ms = time.monotonic()
        response = await self._client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        duration_ms = int((time.monotonic() - start_ms) * 1000)

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = _calculate_cost(resolved_model, input_tokens, output_tokens)

        # Extract text from response content blocks
        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        return response_text, input_tokens, output_tokens, cost_usd


def _inject_images(
    messages: list[dict], images: list[bytes]
) -> list[dict]:
    """Prepend base64-encoded images to the last user message.

    Claude's vision API expects image_url content blocks alongside text.
    We inject them before the text so the model 'sees' the image first,
    which improves layout analysis accuracy.
    """
    messages = [m.copy() for m in messages]

    image_blocks = []
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        # Detect MIME type from magic bytes
        if img_bytes[:2] == b"\xff\xd8":
            media_type = "image/jpeg"
        elif img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            media_type = "image/png"
        elif img_bytes[:4] == b"GIF8":
            media_type = "image/gif"
        elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
            media_type = "image/webp"
        else:
            media_type = "image/png"
        image_blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            }
        )

    # Find the last user message and convert to multi-content format
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            existing_content = messages[i]["content"]
            if isinstance(existing_content, str):
                text_block = {"type": "text", "text": existing_content}
                messages[i]["content"] = image_blocks + [text_block]
            elif isinstance(existing_content, list):
                messages[i]["content"] = image_blocks + existing_content
            break

    return messages


def _calculate_cost(
    model: str, input_tokens: int, output_tokens: int
) -> float:
    """Calculate USD cost from token counts using the rate table.

    Returns 0.0 for unknown models rather than raising — cost tracking
    is important but should never block the pipeline.
    """
    rates = _COST_PER_MTK.get(model)
    if not rates:
        return 0.0

    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost
