"""Cairo + Pango text rendering — the only place text hits pixels.

Per CLAUDE.md design rules: text in images ALWAYS uses Cairo + Pango,
NEVER the image generation model. This ensures proper kerning, ligatures,
line-height, and font rendering at brand quality.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import cairo

from PIL import Image

# Cairo and Pango are C library bindings — only available when system
# packages (libcairo2-dev, libpango1.0-dev) are installed. The Docker
# image includes them; local dev may not. Graceful fallback to PIL-only
# text rendering when missing.
try:
    import cairo
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False

try:
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo
    HAS_PANGO = True
except (ImportError, ValueError):
    HAS_PANGO = False


def render_text_layer(
    base_image: Image.Image,
    text_elements: list[dict[str, Any]],
    font_path: Path,
) -> Image.Image:
    """Render all text elements onto the base image using Cairo + Pango.

    Each text element specifies content, position, size, weight, colour,
    and alignment. Positions are proportions (0.0-1.0) of canvas size,
    converted to absolute pixels here.
    """
    width, height = base_image.size

    if not HAS_CAIRO:
        # Fallback: render text using PIL's basic text capabilities
        return _render_with_pil_fallback(base_image, text_elements, font_path)

    # Convert PIL image to Cairo surface for text rendering
    surface = _pil_to_cairo_surface(base_image)
    ctx = cairo.Context(surface)

    for elem in text_elements:
        _render_single_element(ctx, elem, font_path, width, height)

    # Convert back to PIL
    return _cairo_surface_to_pil(surface)


def check_font_coverage(
    font_path: Path, texts: list[str]
) -> list[str]:
    """Check which characters in the given texts are unsupported by the font.

    Called before composition starts (PRD section 9) so the user can
    rephrase or acknowledge fallback before any tokens are spent on
    compositing.
    """
    if not HAS_PANGO:
        return []

    unsupported: list[str] = []
    try:
        font_desc = Pango.FontDescription.new()
        font_desc.set_family(font_path.stem)

        # Create a temporary context to test font coverage
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        ctx = cairo.Context(surface)
        layout = PangoCairo.create_layout(ctx)
        layout.set_font_description(font_desc)

        for text in texts:
            for char in text:
                layout.set_text(char, -1)
                # If the layout has no visible ink extents, the char is unsupported
                ink_rect, _ = layout.get_pixel_extents()
                if ink_rect.width == 0 and ink_rect.height == 0 and not char.isspace():
                    if char not in unsupported:
                        unsupported.append(char)
    except Exception:
        # Font check failure shouldn't block the pipeline
        pass

    return unsupported


def _render_single_element(
    ctx: cairo.Context,
    elem: dict[str, Any],
    font_path: Path,
    width: int,
    height: int,
) -> None:
    """Render a single text element with proper typography.

    Uses Pango for line wrapping, kerning, and ligatures when available.
    Falls back to basic Cairo text rendering if Pango is not installed.
    """
    content = elem.get("content", "")
    if not content:
        return

    pos = elem.get("position", {})
    margin = int(0.05 * width)  # 5% margin minimum

    x = int(pos.get("x", 0.0) * width)
    y = int(pos.get("y", 0.0) * height)
    max_width_prop = elem.get("max_width_proportion", 0.8)
    max_width = int(max_width_prop * width)
    font_size = elem.get("font_size_base", 48)
    colour = elem.get("colour", "#000000")
    alignment = elem.get("alignment", "left")
    line_height = elem.get("line_height", 1.2)
    font_weight = elem.get("font_weight", "regular")

    # Clamp position so text stays within canvas with margins
    x = max(margin, min(x, width - margin))
    y = max(margin, min(y, height - margin))

    # Ensure max_width doesn't push text off-canvas
    available_width = width - x - margin
    if max_width > available_width:
        max_width = available_width

    # Ensure max_width is at least 30% of canvas
    min_width = int(0.3 * width)
    if max_width < min_width:
        # Shift x left to make room
        x = max(margin, width - min_width - margin)
        max_width = min_width

    # Set colour
    r, g, b = _hex_to_rgb(colour)
    ctx.set_source_rgb(r, g, b)

    if HAS_PANGO:
        _render_with_pango(
            ctx, content, font_path, font_size, font_weight,
            x, y, max_width, alignment, line_height,
        )
    else:
        _render_with_cairo_basic(
            ctx, content, font_size, x, y, max_width,
        )


def _render_with_pango(
    ctx: cairo.Context,
    content: str,
    font_path: Path,
    font_size: int,
    font_weight: str,
    x: int,
    y: int,
    max_width: int,
    alignment: str,
    line_height: float,
) -> None:
    """Render text using Pango for proper typesetting.

    Pango handles kerning, ligatures, and complex text layout that
    Cairo alone cannot — essential for brand-quality typography.
    """
    layout = PangoCairo.create_layout(ctx)

    font_desc = Pango.FontDescription.new()
    font_desc.set_family(font_path.stem)
    font_desc.set_size(font_size * Pango.SCALE)

    if font_weight == "bold":
        font_desc.set_weight(Pango.Weight.BOLD)
    elif font_weight == "medium":
        font_desc.set_weight(Pango.Weight.MEDIUM)
    else:
        font_desc.set_weight(Pango.Weight.NORMAL)

    layout.set_font_description(font_desc)
    layout.set_text(content, -1)
    layout.set_width(max_width * Pango.SCALE)
    layout.set_spacing(int((line_height - 1.0) * font_size * Pango.SCALE))

    if alignment == "centre" or alignment == "center":
        layout.set_alignment(Pango.Alignment.CENTER)
    elif alignment == "right":
        layout.set_alignment(Pango.Alignment.RIGHT)
    else:
        layout.set_alignment(Pango.Alignment.LEFT)

    ctx.move_to(x, y)
    PangoCairo.show_layout(ctx, layout)


def _render_with_cairo_basic(
    ctx: cairo.Context,
    content: str,
    font_size: int,
    x: int,
    y: int,
    max_width: int,
) -> None:
    """Fallback text rendering using Cairo's toy text API.

    Limited typesetting — no kerning, ligatures, or complex layout.
    Used only when Pango is not available (dev environments).
    """
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(font_size)

    # Simple word wrapping
    words = content.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        extents = ctx.text_extents(test_line)
        if extents.width > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line

    if current_line:
        lines.append(current_line)

    for i, line in enumerate(lines):
        ctx.move_to(x, y + (i + 1) * font_size * 1.2)
        ctx.show_text(line)


def _pil_to_cairo_surface(img: Image.Image) -> cairo.ImageSurface:
    """Convert a PIL Image to a Cairo ImageSurface for text rendering.

    Cairo uses ARGB32 format while PIL uses RGBA — byte order swap
    is needed for correct colour rendering.
    """
    img = img.convert("RGBA")
    width, height = img.size

    # PIL is RGBA, Cairo expects ARGB (premultiplied)
    data = bytearray(img.tobytes("raw", "BGRa"))
    surface = cairo.ImageSurface.create_for_data(
        data, cairo.FORMAT_ARGB32, width, height, width * 4
    )
    return surface


def _cairo_surface_to_pil(surface: cairo.ImageSurface) -> Image.Image:
    """Convert a Cairo ImageSurface back to a PIL Image.

    Reverses the byte order swap from _pil_to_cairo_surface.
    """
    width = surface.get_width()
    height = surface.get_height()
    data = bytes(surface.get_data())

    img = Image.frombytes("RGBA", (width, height), data, "raw", "BGRa")
    return img


def _render_with_pil_fallback(
    base_image: Image.Image,
    text_elements: list[dict[str, Any]],
    font_path: Path,
) -> Image.Image:
    """Last-resort text rendering using PIL when Cairo is unavailable.

    PIL's text rendering is basic — no kerning, ligatures, or proper
    line spacing. Acceptable for local dev/testing, not production.
    Production Docker image always has Cairo installed.
    """
    from PIL import ImageDraw, ImageFont

    img = base_image.copy()
    draw = ImageDraw.Draw(img)
    width, height = img.size

    margin = int(0.05 * width)

    for elem in text_elements:
        content = elem.get("content", "")
        if not content:
            continue

        pos = elem.get("position", {})
        x = max(margin, int(pos.get("x", 0.0) * width))
        y = max(margin, int(pos.get("y", 0.0) * height))
        x = min(x, width - margin)
        y = min(y, height - margin)
        font_size = elem.get("font_size_base", 48)
        colour = elem.get("colour", "#000000")

        try:
            font = ImageFont.truetype(str(font_path), font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        draw.text((x, y), content, fill=colour, font=font)

    return img


def _hex_to_rgb(hex_colour: str) -> tuple[float, float, float]:
    """Convert hex colour to Cairo's 0.0-1.0 RGB tuple.

    Cairo uses normalised floats instead of 0-255 integers.
    """
    hex_colour = hex_colour.lstrip("#")
    if len(hex_colour) == 3:
        hex_colour = "".join(c * 2 for c in hex_colour)
    r = int(hex_colour[0:2], 16) / 255.0
    g = int(hex_colour[2:4], 16) / 255.0
    b = int(hex_colour[4:6], 16) / 255.0
    return (r, g, b)
