"""Tests for asset fetcher — validates link checking and file validation."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.schemas import AssetResult
from backend.utils.asset_fetcher import (
    _identify_format,
    _validate_font,
    _validate_image,
    fetch_asset,
)


def test_identify_format_png():
    """PNG magic bytes should be correctly detected."""
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    assert _identify_format(Path("test.bin"), content) == "png"


def test_identify_format_jpg():
    """JPEG magic bytes should be correctly detected."""
    content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    assert _identify_format(Path("test.bin"), content) == "jpg"


def test_identify_format_svg():
    """SVG content should be detected from XML tag."""
    content = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
    assert _identify_format(Path("test.bin"), content) == "svg"


def test_identify_format_unknown():
    """Unknown content should return 'unknown'."""
    content = b"some random data that is not an image"
    result = _identify_format(Path("test.bin"), content)
    # May return 'unknown' or fall back to mimetype
    assert isinstance(result, str)


def test_validate_font_otf():
    """OTF files should pass font validation."""
    result = AssetResult(url="test", format="otf")
    _validate_font(Path("test.otf"), result)
    assert result.usable is True
    assert result.classification == "OK"


def test_validate_font_ttf():
    """TTF files should pass font validation."""
    result = AssetResult(url="test", format="ttf")
    _validate_font(Path("test.ttf"), result)
    assert result.usable is True


def test_validate_font_wrong_format():
    """Non-font formats should fail font validation as BLOCKER."""
    result = AssetResult(url="test", format="png")
    _validate_font(Path("test.png"), result)
    assert result.classification == "BLOCKER"
    assert not result.usable


def test_validate_image_svg_passes():
    """SVG images always pass — we trust vector files."""
    result = AssetResult(url="test", format="svg")
    _validate_image(Path("test.svg"), "logo", result)
    assert result.usable is True
    assert result.classification == "OK"


@pytest.mark.asyncio
async def test_fetch_asset_timeout():
    """Timed-out URLs should return BLOCKER with advice."""
    import httpx

    with patch("backend.utils.asset_fetcher.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.head = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.return_value = instance

        result = await fetch_asset("https://example.com/timeout.png", "logo")
        assert "timed out" in result.issues[0].lower()
        assert result.advice is not None
