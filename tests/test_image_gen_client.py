"""Tests for the image generation provider chain (Google → Pollinations)."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.utils import image_gen_client as igc

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_PNG_B64 = base64.b64encode(_PNG_BYTES).decode()


def _resp(status=200, json_data=None, content=b"", content_type="application/json"):
    """Build a mock httpx.Response with sync raise_for_status/json."""
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.content = content
    r.headers = {"content-type": content_type}

    def _raise():
        if status >= 400:
            import httpx

            raise httpx.HTTPStatusError("err", request=MagicMock(), response=r)

    r.raise_for_status = MagicMock(side_effect=_raise)
    return r


def _client_ctx(get=None, post=None):
    """Mock httpx.AsyncClient context manager with given get/post handlers."""
    instance = AsyncMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    if get is not None:
        instance.get = get
    if post is not None:
        instance.post = post
    return MagicMock(return_value=instance)


def test_aspect_ratio_mapping():
    assert igc._aspect_ratio(1080, 1080) == "1:1"
    assert igc._aspect_ratio(1920, 1080) == "16:9"
    assert igc._aspect_ratio(1080, 1350) == "4:5"
    assert igc._aspect_ratio(1000, 0) == "1:1"


def test_extract_gemini_image_camel_and_snake():
    camel = {"candidates": [{"content": {"parts": [{"inlineData": {"data": _PNG_B64}}]}}]}
    snake = {"candidates": [{"content": {"parts": [{"inline_data": {"data": _PNG_B64}}]}}]}
    assert igc._extract_gemini_image(camel) == _PNG_BYTES
    assert igc._extract_gemini_image(snake) == _PNG_BYTES
    assert igc._extract_gemini_image({"candidates": []}) is None


@pytest.mark.asyncio
async def test_google_success(monkeypatch, tmp_path):
    """A valid Gemini response is decoded and written to disk."""
    monkeypatch.setattr(igc.settings, "google_ai_api_key", "test-key")
    monkeypatch.setattr(igc.settings, "nano_banana_model", "gemini-2.5-flash-image")
    json_data = {
        "candidates": [{"content": {"parts": [{"inlineData": {"data": _PNG_B64}}]}}]
    }
    post = AsyncMock(return_value=_resp(200, json_data))
    with patch("backend.utils.image_gen_client.httpx.AsyncClient", _client_ctx(post=post)):
        path = await igc._gen_google("a cafe", 1080, 1080, tmp_path)
    assert path is not None and path.read_bytes() == _PNG_BYTES
    assert post.await_count == 1  # first config accepted, no retry


@pytest.mark.asyncio
async def test_google_retries_on_400(monkeypatch, tmp_path):
    """A 400 on the first generationConfig retries the next candidate."""
    monkeypatch.setattr(igc.settings, "google_ai_api_key", "test-key")
    json_data = {
        "candidates": [{"content": {"parts": [{"inlineData": {"data": _PNG_B64}}]}}]
    }
    post = AsyncMock(side_effect=[_resp(400), _resp(200, json_data)])
    with patch("backend.utils.image_gen_client.httpx.AsyncClient", _client_ctx(post=post)):
        path = await igc._gen_google("a cafe", 1080, 1080, tmp_path)
    assert path is not None
    assert post.await_count == 2  # retried after the 400


@pytest.mark.asyncio
async def test_google_skipped_without_key(monkeypatch, tmp_path):
    monkeypatch.setattr(igc.settings, "google_ai_api_key", "")
    assert await igc._gen_google("x", 1080, 1080, tmp_path) is None


@pytest.mark.asyncio
async def test_pollinations_success(monkeypatch, tmp_path):
    get = AsyncMock(return_value=_resp(200, content=_PNG_BYTES, content_type="image/jpeg"))
    with patch("backend.utils.image_gen_client.httpx.AsyncClient", _client_ctx(get=get)):
        path = await igc._gen_pollinations("a cafe", 1080, 1080, tmp_path)
    assert path is not None and path.read_bytes() == _PNG_BYTES


@pytest.mark.asyncio
async def test_chain_falls_back_to_pollinations(monkeypatch, tmp_path):
    """When Google returns nothing, the chain falls through to Pollinations."""
    monkeypatch.setattr(igc.settings, "image_gen_disabled", False)
    monkeypatch.setattr(igc.settings, "image_gen_provider", "google")
    monkeypatch.setattr(igc.settings, "image_gen_fallback", "pollinations")
    monkeypatch.setattr(igc.settings, "output_dir", tmp_path)

    async def _google_none(*a, **k):
        return None

    async def _polli_ok(prompt, w, h, out_dir):
        p = out_dir / "generated_hero.jpg"
        p.write_bytes(_PNG_BYTES)
        return p

    monkeypatch.setattr(igc, "_gen_google", _google_none)
    monkeypatch.setattr(igc, "_gen_pollinations", _polli_ok)

    path = await igc.generate_image("a cafe", (1080, 1080), "job123")
    assert path is not None and path.name == "generated_hero.jpg"


@pytest.mark.asyncio
async def test_chain_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(igc.settings, "image_gen_disabled", True)
    assert await igc.generate_image("x", (1080, 1080), "job1") is None
