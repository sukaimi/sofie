"""Tests for the Pexels stock photo client.

Covers the happy path (mapping, min-width filter, resolution sort) plus
every failure mode that must degrade to an empty list so the pipeline
falls back to generation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.utils.pexels_client import PexelsPhoto, search_photos

# A representative Pexels /v1/search response with three photos:
# one below the min-width threshold, two above (out of resolution order).
_SEARCH_RESPONSE = {
    "photos": [
        {
            "id": 1,
            "width": 800,  # below default min_width — must be filtered out
            "height": 600,
            "src": {"original": "https://img/1.jpg", "large2x": "https://img/1_2x.jpg"},
            "photographer": "Small Sam",
            "photographer_url": "https://pexels.com/@sam",
            "alt": "too small",
        },
        {
            "id": 2,
            "width": 1920,
            "height": 1080,
            "src": {"original": "https://img/2.jpg", "large2x": "https://img/2_2x.jpg"},
            "photographer": "Joey Farina",
            "photographer_url": "https://pexels.com/@joey",
            "alt": "golden hour rocks",
        },
        {
            "id": 3,
            "width": 4000,
            "height": 3000,
            "src": {"original": "https://img/3.jpg", "large2x": "https://img/3_2x.jpg"},
            "photographer": "Ansel A",
            "photographer_url": "https://pexels.com/@ansel",
            "alt": "big landscape",
        },
    ]
}


def _mock_client(response_json: dict) -> MagicMock:
    """Build a mocked httpx.AsyncClient whose GET returns response_json."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=response_json)

    instance = AsyncMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    instance.get = AsyncMock(return_value=resp)

    client_cls = MagicMock(return_value=instance)
    return client_cls


@pytest.mark.asyncio
async def test_search_filters_and_sorts(monkeypatch):
    """Below-min-width photos are dropped; results come widest-first."""
    monkeypatch.setattr(
        "backend.utils.pexels_client.settings.pexels_api_key", "test-key"
    )
    with patch(
        "backend.utils.pexels_client.httpx.AsyncClient",
        _mock_client(_SEARCH_RESPONSE),
    ):
        photos = await search_photos(
            query="golden hour", orientation="landscape", per_page=15, min_width=1080
        )

    assert [p.id for p in photos] == [3, 2]  # 800px dropped, sorted by width desc
    assert all(isinstance(p, PexelsPhoto) for p in photos)
    assert photos[0].photographer == "Ansel A"
    assert photos[1].src_original == "https://img/2.jpg"


@pytest.mark.asyncio
async def test_search_no_key_returns_empty(monkeypatch):
    """Missing key short-circuits before any HTTP call."""
    monkeypatch.setattr("backend.utils.pexels_client.settings.pexels_api_key", "")
    client_cls = _mock_client(_SEARCH_RESPONSE)
    with patch("backend.utils.pexels_client.httpx.AsyncClient", client_cls):
        photos = await search_photos(
            query="anything", orientation="square", per_page=15, min_width=1080
        )
    assert photos == []
    client_cls.assert_not_called()  # no key → no request


@pytest.mark.asyncio
async def test_search_http_error_returns_empty(monkeypatch):
    """Auth/rate-limit/transport errors degrade to an empty list, no raise."""
    monkeypatch.setattr(
        "backend.utils.pexels_client.settings.pexels_api_key", "test-key"
    )
    instance = AsyncMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    instance.get = AsyncMock(side_effect=Exception("401 Unauthorized"))

    with patch(
        "backend.utils.pexels_client.httpx.AsyncClient",
        MagicMock(return_value=instance),
    ):
        photos = await search_photos(
            query="anything", orientation="portrait", per_page=15, min_width=1080
        )
    assert photos == []


@pytest.mark.asyncio
async def test_search_zero_results_returns_empty(monkeypatch):
    """An empty photos array yields an empty list (caller falls back)."""
    monkeypatch.setattr(
        "backend.utils.pexels_client.settings.pexels_api_key", "test-key"
    )
    with patch(
        "backend.utils.pexels_client.httpx.AsyncClient",
        _mock_client({"photos": []}),
    ):
        photos = await search_photos(
            query="nonexistent", orientation="landscape", per_page=15, min_width=1080
        )
    assert photos == []
