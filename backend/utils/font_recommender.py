"""Font recommender — suggests installed system fonts as alternatives.

When a brand font can't be loaded, this maps the font name or style
to the closest available system font. Uses simple keyword matching
against a curated list of installed fonts.
"""

from pathlib import Path

# Fonts installed in the Docker container via apt packages.
# Mapped by style category for smart matching.
AVAILABLE_FONTS: dict[str, dict[str, str]] = {
    "Noto Sans": {
        "path": "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "style": "sans-serif",
        "vibe": "clean, modern, neutral",
    },
    "Roboto": {
        "path": "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
        "style": "sans-serif",
        "vibe": "tech, modern, geometric",
    },
    "Open Sans": {
        "path": "/usr/share/fonts/truetype/open-sans/OpenSans-Regular.ttf",
        "style": "sans-serif",
        "vibe": "friendly, readable, versatile",
    },
    "Lato": {
        "path": "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
        "style": "sans-serif",
        "vibe": "warm, professional, semi-rounded",
    },
    "Montserrat": {
        "path": "/usr/share/fonts/truetype/montserrat/Montserrat-Regular.otf",
        "style": "sans-serif",
        "vibe": "bold, urban, geometric",
    },
    "DejaVu Sans": {
        "path": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "style": "sans-serif",
        "vibe": "system default, wide coverage",
    },
}


def recommend_font(brand_name: str, font_name_hint: str = "") -> list[dict[str, str]]:
    """Recommend up to 3 installed fonts based on brand context.

    Returns a list of {name, path, reason} dicts sorted by relevance.
    """
    hint = font_name_hint.lower()
    recommendations = []

    for name, info in AVAILABLE_FONTS.items():
        if not Path(info["path"]).exists():
            continue

        # Score based on keyword matching
        score = 0
        name_lower = name.lower()

        # Direct name similarity
        if hint and any(word in name_lower for word in hint.split()):
            score += 10

        # Style matching from hint keywords
        if any(kw in hint for kw in ("sans", "clean", "modern", "minimal")):
            if info["style"] == "sans-serif":
                score += 5
        if any(kw in hint for kw in ("serif", "elegant", "classic", "traditional")):
            if info["style"] == "serif":
                score += 5
        if any(kw in hint for kw in ("bold", "strong", "impact", "sport")):
            if "bold" in info["vibe"] or "geometric" in info["vibe"]:
                score += 5
        if any(kw in hint for kw in ("warm", "friendly", "soft")):
            if "warm" in info["vibe"] or "friendly" in info["vibe"]:
                score += 5

        # Default: prefer Noto Sans and Montserrat as versatile options
        if name == "Noto Sans":
            score += 2
        if name == "Montserrat":
            score += 1

        # Deprioritise DejaVu (system default)
        if name == "DejaVu Sans":
            score -= 3

        recommendations.append({
            "name": name,
            "path": info["path"],
            "vibe": info["vibe"],
            "score": score,
        })

    recommendations.sort(key=lambda r: r["score"], reverse=True)

    return [
        {"name": r["name"], "path": r["path"], "reason": r["vibe"]}
        for r in recommendations[:3]
    ]


def get_font_path(font_name: str) -> str | None:
    """Get the path for a font by name. Returns None if not found."""
    for name, info in AVAILABLE_FONTS.items():
        if name.lower() == font_name.lower() and Path(info["path"]).exists():
            return info["path"]
    return None
