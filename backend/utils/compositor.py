"""Pillow compositing functions — Kai's execution engine.

Takes Celeste's composition plan (proportional coordinates) and
renders it to absolute pixels. Handles background, overlays, hero
image, design elements, and logo placement. Text is handled
separately by text_renderer.py via Cairo.
"""

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


def composite(
    plan: dict[str, Any],
    assets: dict[str, str],
    output_path: Path,
    dimensions: tuple[int, int],
    jpg_quality: int = 92,
) -> Path:
    """Execute a composition plan to produce a layered image.

    Layers are applied bottom-to-top per PRD section 11:
    background → overlay → pattern → hero → elements → logo.
    Text layers are added by text_renderer after this returns.
    """
    width, height = dimensions
    canvas = Image.new("RGBA", (width, height), _parse_colour(plan.get("canvas_colour", "#FFFFFF")))

    # Layer 2: colour overlay
    overlay_colour = plan.get("overlay_colour")
    overlay_opacity = plan.get("overlay_opacity", 0.0)
    if overlay_colour and overlay_opacity > 0:
        canvas = _apply_overlay(canvas, overlay_colour, overlay_opacity)

    # Layer 3: brand pattern/texture
    pattern_path = assets.get("pattern") or assets.get("texture")
    if pattern_path and Path(pattern_path).exists():
        canvas = _apply_pattern(canvas, Path(pattern_path), width, height)

    # Layer 4: hero image
    hero_plan = plan.get("hero_image", {})
    hero_path = assets.get("hero")
    if hero_path and Path(hero_path).exists():
        canvas = _place_hero(canvas, Path(hero_path), hero_plan, width, height)

    # Layer 5: design elements
    for i, elem_plan in enumerate(plan.get("design_elements", [])):
        elem_path = assets.get(f"element_{i}") or elem_plan.get("path")
        if elem_path and Path(elem_path).exists():
            canvas = _place_element(canvas, Path(elem_path), elem_plan, width, height)

    # Layer 6: logo
    logo_plan = plan.get("logo", {})
    logo_path = assets.get("logo")
    if logo_path and Path(logo_path).exists():
        canvas = _place_logo(canvas, Path(logo_path), logo_plan, width, height)

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in (".jpg", ".jpeg"):
        rgb_canvas = canvas.convert("RGB")
        rgb_canvas.save(str(output_path), "JPEG", quality=jpg_quality)
    else:
        canvas.save(str(output_path), "PNG")

    return output_path


def _parse_colour(hex_colour: str) -> tuple[int, int, int, int]:
    """Convert hex colour string to RGBA tuple.

    Handles both 3-char (#FFF) and 6-char (#FFFFFF) hex codes.
    Returns opaque alpha by default.
    """
    hex_colour = hex_colour.lstrip("#")
    if len(hex_colour) == 3:
        hex_colour = "".join(c * 2 for c in hex_colour)
    if len(hex_colour) == 6:
        r, g, b = int(hex_colour[0:2], 16), int(hex_colour[2:4], 16), int(hex_colour[4:6], 16)
        return (r, g, b, 255)
    return (255, 255, 255, 255)


def _apply_overlay(
    canvas: Image.Image, colour: str, opacity: float
) -> Image.Image:
    """Apply a semi-transparent colour overlay to the canvas.

    Used for tinting hero images or creating branded colour washes
    that tie the composition together.
    """
    r, g, b, _ = _parse_colour(colour)
    alpha = int(255 * min(max(opacity, 0.0), 1.0))
    overlay = Image.new("RGBA", canvas.size, (r, g, b, alpha))
    return Image.alpha_composite(canvas, overlay)


def _apply_pattern(
    canvas: Image.Image, pattern_path: Path, width: int, height: int
) -> Image.Image:
    """Tile a pattern/texture across the canvas.

    Patterns are tiled rather than stretched so they maintain their
    intended visual density regardless of canvas size.
    """
    pattern = Image.open(pattern_path).convert("RGBA")
    for y in range(0, height, pattern.height):
        for x in range(0, width, pattern.width):
            canvas.paste(pattern, (x, y), pattern)
    return canvas


def _place_hero(
    canvas: Image.Image,
    hero_path: Path,
    plan: dict[str, Any],
    width: int,
    height: int,
) -> Image.Image:
    """Resize and position the hero image per the composition plan.

    Crop focus determines which part of the image is preserved when
    aspect ratios don't match — 'centre' keeps the middle,
    'top' preserves the top edge, etc.
    """
    hero = Image.open(hero_path).convert("RGBA")
    pos = plan.get("position", {})

    target_w = int(pos.get("width", 1.0) * width)
    target_h = int(pos.get("height", 1.0) * height)
    target_x = int(pos.get("x", 0.0) * width)
    target_y = int(pos.get("y", 0.0) * height)

    # Resize maintaining aspect ratio, then crop to target
    hero = _resize_and_crop(hero, target_w, target_h, plan.get("crop_focus", "centre"))

    # Apply opacity if specified
    opacity = plan.get("opacity", 1.0)
    if opacity < 1.0:
        hero.putalpha(int(255 * opacity))

    canvas.paste(hero, (target_x, target_y), hero)
    return canvas


def _place_element(
    canvas: Image.Image,
    elem_path: Path,
    plan: dict[str, Any],
    width: int,
    height: int,
) -> Image.Image:
    """Position a design element (frame, graphic device, etc).

    Elements are sized as a proportion of canvas width and positioned
    at the specified coordinates.
    """
    elem = Image.open(elem_path).convert("RGBA")
    pos = plan.get("position", {})
    size_prop = plan.get("size_proportion", 0.3)

    target_w = int(size_prop * width)
    ratio = target_w / elem.width
    target_h = int(elem.height * ratio)
    elem = elem.resize((target_w, target_h), Image.LANCZOS)

    x = int(pos.get("x", 0.0) * width)
    y = int(pos.get("y", 0.0) * height)

    opacity = plan.get("opacity", 1.0)
    if opacity < 1.0:
        elem.putalpha(int(255 * opacity))

    canvas.paste(elem, (x, y), elem)
    return canvas


def _place_logo(
    canvas: Image.Image,
    logo_path: Path,
    plan: dict[str, Any],
    width: int,
    height: int,
) -> Image.Image:
    """Position the logo per the composition plan.

    Logo is sized as a proportion of canvas width. Anchor determines
    which corner or edge the position coordinates refer to.
    """
    logo = Image.open(logo_path).convert("RGBA")
    size_prop = plan.get("size_proportion", 0.15)
    pos = plan.get("position", {})
    anchor = plan.get("anchor", "bottom-right")

    target_w = int(size_prop * width)
    ratio = target_w / logo.width
    target_h = int(logo.height * ratio)
    logo = logo.resize((target_w, target_h), Image.LANCZOS)

    # Calculate position based on anchor
    base_x = int(pos.get("x", 0.85) * width)
    base_y = int(pos.get("y", 0.9) * height)

    if "right" in anchor:
        base_x -= target_w
    if "bottom" in anchor:
        base_y -= target_h
    if anchor == "centre":
        base_x -= target_w // 2
        base_y -= target_h // 2

    canvas.paste(logo, (base_x, base_y), logo)
    return canvas


def _resize_and_crop(
    img: Image.Image, target_w: int, target_h: int, focus: str
) -> Image.Image:
    """Resize image to cover target area, then crop to exact size.

    'Cover' means the image is scaled so the smallest dimension
    matches the target, then the excess is cropped based on focus.
    """
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        # Image is wider — scale by height, crop width
        new_h = target_h
        new_w = int(img.width * (target_h / img.height))
    else:
        # Image is taller — scale by width, crop height
        new_w = target_w
        new_h = int(img.height * (target_w / img.width))

    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Crop based on focus
    if focus == "top":
        return img.crop((0, 0, target_w, target_h))
    elif focus == "bottom":
        return img.crop((0, new_h - target_h, target_w, new_h))
    elif focus == "left":
        return img.crop((0, 0, target_w, target_h))
    elif focus == "right":
        return img.crop((new_w - target_w, 0, new_w, target_h))
    else:  # centre
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))
