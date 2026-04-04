"""
Step 5: Compositor
Layers all elements into the final composition using Pillow.
Ported from archived/src/step3_compositor.py with async wrapper.
Layering order: base -> overlay -> elements -> hero -> logo -> headline -> sub-copy -> CTA
"""

import asyncio
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def _parse_dimensions(dims: str) -> tuple[int, int]:
    w, h = dims.lower().split("x")
    return int(w), int(h)


def _parse_colour_overlay(spec: str | None) -> tuple[tuple[int, int, int], int] | None:
    if not spec:
        return None
    parts = spec.split(" at ")
    if len(parts) != 2:
        return None
    hex_color = parts[0].strip().lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    opacity_pct = int(parts[1].replace("%", "").replace("opacity", "").strip())
    alpha = int(255 * opacity_pct / 100)
    return (r, g, b), alpha


def _load_font(font_path: Path | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path and font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except OSError:
        return ImageFont.load_default()


def _find_font(brand_dir: Path, font_name: str | None) -> Path | None:
    if not font_name:
        return None
    assets_dir = brand_dir / "assets"

    direct = assets_dir / font_name
    if direct.exists():
        return direct

    fonts_dir = assets_dir / "fonts"
    if fonts_dir.exists():
        candidate = fonts_dir / font_name
        if candidate.exists():
            return candidate
        for f in fonts_dir.iterdir():
            if f.suffix.lower() in (".otf", ".ttf"):
                return f

    for f in assets_dir.iterdir():
        if f.suffix.lower() in (".otf", ".ttf"):
            return f

    return None


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _get_text_color(brand_md: str | None, fallback: str = "#FFFFFF") -> str:
    if brand_md:
        for line in brand_md.split("\n"):
            if "text:" in line.lower() and "#" in line:
                start = line.index("#")
                return line[start : start + 7]
    return fallback


def _get_accent_color(brand_md: str | None, fallback: str = "#FF6600") -> str:
    if brand_md:
        for line in brand_md.split("\n"):
            if "accent:" in line.lower() and "#" in line:
                start = line.index("#")
                return line[start : start + 7]
    return fallback


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    shadow_offset: int = 2,
) -> None:
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=fill)


def _compose_sync(
    prompt_package: dict,
    brand_dir: Path,
    raw_image_path: Path,
    output_dir: Path,
) -> Path:
    """Synchronous composition — runs in thread via asyncio.to_thread."""
    width, height = _parse_dimensions(prompt_package.get("output_dimensions", "1080x1080"))
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    assets_dir = brand_dir / "assets"

    # Layer 1: Base image
    if raw_image_path.exists():
        base = Image.open(raw_image_path).convert("RGBA").resize((width, height), Image.LANCZOS)
        canvas.paste(base, (0, 0))

    # Layer 2: Colour overlay
    overlay_data = _parse_colour_overlay(prompt_package.get("colour_overlay"))
    if overlay_data:
        (r, g, b), alpha = overlay_data
        overlay = Image.new("RGBA", (width, height), (r, g, b, alpha))
        canvas = Image.alpha_composite(canvas, overlay)

    # Layer 3: Design elements
    for elem_name in prompt_package.get("elements", []):
        elem_path = assets_dir / "elements" / elem_name
        if elem_path.exists():
            elem = Image.open(elem_path).convert("RGBA")
            elem.thumbnail((width // 2, height // 2), Image.LANCZOS)
            x = (width - elem.width) // 2
            y = (height - elem.height) // 2
            canvas.paste(elem, (x, y), elem)

    # Layer 4: Hero image
    hero_name = prompt_package.get("hero_image")
    if hero_name:
        hero_path = assets_dir / "images" / hero_name
        if hero_path.exists():
            hero = Image.open(hero_path).convert("RGBA")
            hero.thumbnail((int(width * 0.6), int(height * 0.6)), Image.LANCZOS)
            x = (width - hero.width) // 2
            y = (height - hero.height) // 2
            canvas.paste(hero, (x, y), hero)

    # Layer 5: Logo
    logo_name = prompt_package.get("logo")
    if logo_name:
        logo_path = assets_dir / logo_name
        if logo_path.exists():
            logo = Image.open(logo_path).convert("RGBA")
            logo_max = int(min(width, height) * 0.15)
            logo.thumbnail((logo_max, logo_max), Image.LANCZOS)

            placement = prompt_package.get("logo_placement", "bottom-right")
            padding = int(width * 0.04)

            ly = padding if "top" in placement else height - logo.height - padding
            if "left" in placement:
                lx = padding
            elif "centre" in placement or "center" in placement:
                lx = (width - logo.width) // 2
            else:
                lx = width - logo.width - padding

            canvas.paste(logo, (lx, ly), logo)

    # Layers 6-8: Text overlays
    brand_md_path = brand_dir / "brand.md"
    brand_md = brand_md_path.read_text() if brand_md_path.exists() else None

    font_path = _find_font(brand_dir, prompt_package.get("font"))
    text_color = _hex_to_rgb(_get_text_color(brand_md))
    accent_color = _hex_to_rgb(_get_accent_color(brand_md))

    draw = ImageDraw.Draw(canvas)
    padding = int(width * 0.06)
    headline_placement = prompt_package.get("headline_placement", "top")

    # Layer 6: Headline
    headline = prompt_package.get("headline_text")
    if headline:
        headline_font = _load_font(font_path, int(height * 0.06))
        bbox = draw.textbbox((0, 0), headline, font=headline_font)
        text_w = bbox[2] - bbox[0]

        if headline_placement == "top":
            ty = padding
        elif headline_placement in ("centre", "center"):
            ty = (height - (bbox[3] - bbox[1])) // 2
        else:
            ty = height - (bbox[3] - bbox[1]) - padding - int(height * 0.15)

        tx = (width - text_w) // 2
        _draw_text_with_shadow(draw, (tx, ty), headline, headline_font, text_color)
        last_text_y = ty + (bbox[3] - bbox[1])
    else:
        last_text_y = padding

    # Layer 7: Sub-copy
    sub_copy = prompt_package.get("sub_copy")
    if sub_copy:
        sub_font = _load_font(font_path, int(height * 0.035))
        bbox = draw.textbbox((0, 0), sub_copy, font=sub_font)
        text_w = bbox[2] - bbox[0]
        tx = (width - text_w) // 2
        ty = last_text_y + int(height * 0.03)
        _draw_text_with_shadow(draw, (tx, ty), sub_copy, sub_font, text_color)
        last_text_y = ty + (bbox[3] - bbox[1])

    # Layer 8: CTA
    cta = prompt_package.get("cta")
    if cta:
        cta_font = _load_font(font_path, int(height * 0.04))
        bbox = draw.textbbox((0, 0), cta, font=cta_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        btn_padding_x = int(width * 0.04)
        btn_padding_y = int(height * 0.015)
        btn_w = text_w + btn_padding_x * 2
        btn_h = text_h + btn_padding_y * 2
        btn_x = (width - btn_w) // 2
        btn_y = last_text_y + int(height * 0.04)

        btn_rect = [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h]
        draw.rounded_rectangle(btn_rect, radius=10, fill=accent_color + (230,))

        tx = btn_x + btn_padding_x
        ty = btn_y + btn_padding_y
        draw.text((tx, ty), cta, font=cta_font, fill=(255, 255, 255))

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "final.png"
    final = canvas.convert("RGB")
    final.save(str(output_path), "PNG")

    logger.info(f"Composited image saved: {output_path}")
    return output_path


async def run(
    prompt_package: dict,
    brand_dir: Path,
    raw_image_path: Path,
    job_id: str,
) -> Path:
    """Compose the final image from all layers (async wrapper).

    Returns path to the composited final image.
    """
    from backend.config import settings

    output_dir = settings.output_dir / job_id
    return await asyncio.to_thread(
        _compose_sync, prompt_package, brand_dir, raw_image_path, output_dir
    )
