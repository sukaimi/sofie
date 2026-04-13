"""Tests for Pillow compositor — validates layer composition."""

from pathlib import Path

import pytest
from PIL import Image

from backend.utils.compositor import (
    _parse_colour,
    _apply_overlay,
    _resize_and_crop,
    composite,
)


def test_parse_colour_six_char():
    """Standard 6-char hex should return correct RGBA."""
    assert _parse_colour("#FF0000") == (255, 0, 0, 255)
    assert _parse_colour("#00FF00") == (0, 255, 0, 255)
    assert _parse_colour("#0000FF") == (0, 0, 255, 255)


def test_parse_colour_three_char():
    """3-char shorthand hex should expand correctly."""
    assert _parse_colour("#FFF") == (255, 255, 255, 255)
    assert _parse_colour("#000") == (0, 0, 0, 255)


def test_parse_colour_without_hash():
    """Hex without # prefix should still work."""
    assert _parse_colour("FF0000") == (255, 0, 0, 255)


def test_apply_overlay():
    """Overlay should blend a semi-transparent colour onto canvas."""
    canvas = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
    result = _apply_overlay(canvas, "#000000", 0.5)
    # Result should be darker than pure white
    pixel = result.getpixel((50, 50))
    assert pixel[0] < 255  # Red channel should be reduced
    assert pixel[3] == 255  # Alpha should be fully opaque


def test_apply_overlay_zero_opacity():
    """Zero opacity overlay should not change the canvas."""
    canvas = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
    result = _apply_overlay(canvas, "#000000", 0.0)
    pixel = result.getpixel((50, 50))
    assert pixel == (255, 255, 255, 255)


def test_resize_and_crop_centre():
    """Centre crop should preserve the middle of the image."""
    img = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
    result = _resize_and_crop(img, 100, 100, "centre")
    assert result.size == (100, 100)


def test_resize_and_crop_top():
    """Top crop should preserve the top edge."""
    img = Image.new("RGBA", (100, 200), (0, 255, 0, 255))
    result = _resize_and_crop(img, 100, 100, "top")
    assert result.size == (100, 100)


def test_composite_creates_file(tmp_path):
    """Composite should create an output file at the specified path."""
    plan = {
        "canvas_colour": "#1a1a2e",
        "overlay_colour": None,
        "overlay_opacity": 0.0,
        "hero_image": {},
        "logo": {},
        "design_elements": [],
        "text_elements": [],
    }
    output_path = tmp_path / "test_output.jpg"
    result = composite(plan, {}, output_path, (1080, 1080))

    assert result.exists()
    img = Image.open(result)
    assert img.size == (1080, 1080)


def test_composite_png_format(tmp_path):
    """Composite should save as PNG when extension is .png."""
    plan = {
        "canvas_colour": "#FFFFFF",
        "overlay_colour": None,
        "overlay_opacity": 0.0,
        "hero_image": {},
        "logo": {},
        "design_elements": [],
        "text_elements": [],
    }
    output_path = tmp_path / "test_output.png"
    result = composite(plan, {}, output_path, (500, 500))

    assert result.exists()
    img = Image.open(result)
    assert img.mode == "RGBA"


def test_composite_with_overlay(tmp_path):
    """Composite with overlay should tint the canvas."""
    plan = {
        "canvas_colour": "#FFFFFF",
        "overlay_colour": "#FF0000",
        "overlay_opacity": 0.5,
        "hero_image": {},
        "logo": {},
        "design_elements": [],
        "text_elements": [],
    }
    output_path = tmp_path / "overlay_test.jpg"
    result = composite(plan, {}, output_path, (100, 100))

    img = Image.open(result)
    pixel = img.getpixel((50, 50))
    # Should be pinkish (white + 50% red overlay)
    assert pixel[0] > pixel[2]  # Red > Blue
