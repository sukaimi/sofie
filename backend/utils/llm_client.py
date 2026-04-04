import base64
import json
import logging
import re

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(300.0, connect=10.0),
        )
    return _client


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences from JSON responses."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _strip_thinking_tags(text: str) -> str:
    """Strip <think>...</think> tags from model responses (Qwen 3 etc.)."""
    return re.sub(r"<think>[\s\S]*?</think>\s*", "", text).strip()


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    response_format: str | None = None,
    images: list[bytes] | None = None,
    temperature: float = 0.7,
) -> str:
    """Call Ollama's OpenAI-compatible chat completion endpoint.

    Args:
        messages: List of {"role": ..., "content": ...} dicts.
        model: Model name. Defaults to settings.llm_model.
        response_format: Set to "json_object" for structured JSON output.
        images: List of raw image bytes for vision models.
        temperature: Sampling temperature.

    Returns:
        The assistant's response text.
    """
    model = model or settings.llm_model
    client = _get_client()

    # If images provided, use Ollama's native /api/chat for vision
    if images:
        return await _vision_chat(client, messages, model, images, temperature)

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    if response_format == "json_object":
        payload["format"] = "json"

    for attempt in range(3):
        try:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]
            content = _strip_thinking_tags(content)
            return content
        except (httpx.HTTPStatusError, httpx.ConnectError, KeyError) as e:
            logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise
    return ""


async def _vision_chat(
    client: httpx.AsyncClient,
    messages: list[dict],
    model: str,
    images: list[bytes],
    temperature: float,
) -> str:
    """Call Ollama's /api/chat with images for vision models."""
    b64_images = [base64.b64encode(img).decode("utf-8") for img in images]

    # Attach images to the last user message
    ollama_messages = []
    for msg in messages:
        m = {"role": msg["role"], "content": msg["content"]}
        ollama_messages.append(m)

    if ollama_messages:
        ollama_messages[-1]["images"] = b64_images

    payload = {
        "model": model,
        "messages": ollama_messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    resp = await client.post("/api/chat", json=payload)
    resp.raise_for_status()
    data = resp.json()
    content = data["message"]["content"]
    return _strip_thinking_tags(content)


async def parse_json_response(
    messages: list[dict],
    model: str | None = None,
    images: list[bytes] | None = None,
) -> dict:
    """Call LLM and parse the response as JSON."""
    raw = await chat_completion(
        messages,
        model=model,
        response_format="json_object" if not images else None,
        images=images,
        temperature=0.3,
    )
    cleaned = _strip_json_fences(raw)
    return json.loads(cleaned)


async def check_health() -> bool:
    """Check if Ollama is reachable."""
    try:
        client = _get_client()
        resp = await client.get("/api/tags")
        return resp.status_code == 200
    except Exception:
        return False
