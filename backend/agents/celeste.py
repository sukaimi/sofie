"""Celeste — Art Director agent.

Interprets layout references, analyses brand context, and produces a
precise composition plan for Kai to execute. Uses Opus vision for
high-accuracy proportional layout extraction.
"""

import json
from typing import Any

from backend.agents.base import BaseAgent
from backend.models import Job


class CelesteAgent(BaseAgent):
    """Art director — translates briefs and references into composition plans.

    Celeste thinks in proportions and relationships. Her output is a
    pixel-precise JSON plan that Kai can execute mechanically. She owns
    the creative vision; Kai owns the execution.
    """

    name = "celeste"
    model = "opus"
    system_prompt = (
        "You are Celeste, an art director at a creative studio.\n\n"
        "You receive: a validated brief, brand assets, and layout references.\n"
        "You produce: a precise composition plan as JSON.\n\n"
        "REFERENCE ANALYSIS (if references provided):\n"
        "- 'Replicate this': copy layout structure closely\n"
        "- 'Layout reference': extract spatial logic only, not style\n"
        "- 'Mood reference': extract tone, feeling, energy only\n\n"
        "Extract proportional positions (0.0 to 1.0) for all elements.\n\n"
        "If no references, design the layout from:\n"
        "- Brand guidelines (tone, style, colour)\n"
        "- Platform specs (IG square vs LinkedIn landscape)\n"
        "- Best practice for the campaign objective\n\n"
        "Output ONLY valid JSON with this structure:\n"
        "{\n"
        '  "layout_type": "hero_dominant|text_dominant|split|diagonal|centred",\n'
        '  "canvas_colour": "#hex",\n'
        '  "overlay_colour": "#hex or null",\n'
        '  "overlay_opacity": 0.0-1.0,\n'
        '  "hero_image": {"position": {"x":0,"y":0,"width":1,"height":1}, '
        '"crop_focus": "centre", "opacity": 1.0},\n'
        '  "logo": {"position": {"x":0,"y":0}, "size_proportion": 0.15, '
        '"anchor": "bottom-right"},\n'
        '  "design_elements": [],\n'
        '  "text_elements": [\n'
        "    {\n"
        '      "role": "headline|subcopy|cta|mandatory",\n'
        '      "content": "...",\n'
        '      "position": {"x": 0.0, "y": 0.0},\n'
        '      "max_width_proportion": 0.6,\n'
        '      "font_size_base": 72,\n'
        '      "font_weight": "bold|medium|regular",\n'
        '      "colour": "#hex",\n'
        '      "alignment": "left|centre|right",\n'
        '      "line_height": 1.2\n'
        "    }\n"
        "  ],\n"
        '  "rationale": "Plain language explanation"\n'
        "}\n\n"
        "All positions as proportions of canvas (0.0 to 1.0).\n\n"
        "CRITICAL: text_elements must NEVER be empty. If the brief has a "
        "headline, sub-copy, or CTA, you MUST include them as text_elements. "
        "Always include at least the headline. Use the brand colours for text. "
        "If no brand colours are specified, use white text on dark backgrounds "
        "or dark text on light backgrounds."
    )

    async def execute(
        self, job: Job, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyse references and brief to produce a composition plan.

        Sends reference images via vision when available — Celeste
        extracts proportional layouts from them. Without references,
        she designs from brand guidelines and platform best practice.
        """
        brief = input_data.get("brief_fields", {})
        assets = input_data.get("assets", [])
        dimensions = input_data.get("dimensions", "1080x1080")

        # Collect reference images for vision analysis — only actual images
        reference_images: list[bytes] = []
        reference_descriptions: list[str] = []
        for asset in assets:
            if asset.get("identified_type") == "reference" and asset.get("local_path"):
                if asset.get("format") not in ("png", "jpg", "jpeg"):
                    continue
                try:
                    with open(asset["local_path"], "rb") as f:
                        data = f.read()
                    # Verify it's actually an image via magic bytes
                    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:2] == b"\xff\xd8":
                        reference_images.append(data)
                        reference_descriptions.append(
                            f"Reference image: {asset.get('url', 'unknown')}"
                        )
                except OSError:
                    continue

        prompt = self._build_prompt(brief, assets, dimensions, reference_descriptions)
        messages = [{"role": "user", "content": prompt}]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="art_direction",
            max_tokens=2048,
            images=reference_images if reference_images else None,
        )

        plan = self._parse_plan(response)

        # Enforce text elements from brief if Celeste returned none
        if not plan.get("text_elements"):
            plan["text_elements"] = self._generate_fallback_text(brief)

        # Ensure canvas colour uses brand colours if available
        if plan.get("canvas_colour", "#FFFFFF") == "#FFFFFF" and brief.get("brand_colours"):
            colours = brief["brand_colours"]
            if isinstance(colours, str):
                import re
                match = re.search(r"#[0-9A-Fa-f]{6}", colours)
                if match:
                    plan["canvas_colour"] = match.group()

        job.composition_plan = plan
        await self._session.flush()

        return plan

    def _generate_fallback_text(self, brief: dict) -> list[dict]:
        """Generate text elements from brief fields when Celeste returns none."""
        elements = []
        brand_colours = brief.get("brand_colours", "")

        # Pick contrasting text colour
        text_colour = "#FFFFFF"

        if brief.get("headline_text"):
            elements.append({
                "role": "headline",
                "content": brief["headline_text"],
                "position": {"x": 0.08, "y": 0.35},
                "max_width_proportion": 0.84,
                "font_size_base": 72,
                "font_weight": "bold",
                "colour": text_colour,
                "alignment": "left",
                "line_height": 1.1,
            })

        if brief.get("sub_copy") or brief.get("key_message"):
            content = brief.get("sub_copy") or brief.get("key_message", "")[:80]
            elements.append({
                "role": "subcopy",
                "content": content,
                "position": {"x": 0.08, "y": 0.55},
                "max_width_proportion": 0.84,
                "font_size_base": 28,
                "font_weight": "regular",
                "colour": text_colour,
                "alignment": "left",
                "line_height": 1.3,
            })

        if brief.get("cta_text"):
            elements.append({
                "role": "cta",
                "content": brief["cta_text"].upper(),
                "position": {"x": 0.08, "y": 0.75},
                "max_width_proportion": 0.84,
                "font_size_base": 36,
                "font_weight": "bold",
                "colour": text_colour,
                "alignment": "centre",
                "line_height": 1.2,
            })

        return elements

    async def revise_plan(
        self, job: Job, qa_issues: list[str], current_plan: dict[str, Any]
    ) -> dict[str, Any]:
        """Revise the composition plan based on Dana's QA feedback.

        Takes specific issues from QA (e.g. 'headline not visible enough')
        and adjusts the plan accordingly. This is the QA loop's creative
        decision point — Celeste decides HOW to fix, Kai executes.
        """
        issues_text = "\n".join(f"- {issue}" for issue in qa_issues)
        plan_text = json.dumps(current_plan, indent=2)

        messages = [
            {
                "role": "user",
                "content": (
                    f"QA found these issues with the composition:\n{issues_text}\n\n"
                    f"Current plan:\n{plan_text}\n\n"
                    "Revise the plan to fix these issues. Output the complete "
                    "revised plan as JSON."
                ),
            }
        ]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="plan_revision",
            max_tokens=2048,
        )

        plan = self._parse_plan(response)
        job.composition_plan = plan
        await self._session.flush()

        return plan

    def _build_prompt(
        self,
        brief: dict[str, Any],
        assets: list[dict[str, Any]],
        dimensions: str,
        reference_descriptions: list[str],
    ) -> str:
        """Assemble the art direction prompt from brief and asset data.

        Structured so Celeste sees the most important info first:
        output dimensions, then brand context, then available assets.
        """
        parts = [f"Create a composition plan for a {dimensions} canvas.\n"]

        parts.append(f"Brand: {brief.get('brand_name', 'Unknown')}")
        parts.append(f"Platform: {brief.get('platform', 'Instagram')}")
        parts.append(f"Key message: {brief.get('key_message', '')}")
        parts.append(f"Headline: {brief.get('headline_text', '')}")

        if brief.get("sub_copy"):
            parts.append(f"Sub-copy: {brief['sub_copy']}")
        if brief.get("cta_text"):
            parts.append(f"CTA: {brief['cta_text']}")
        if brief.get("brand_colours"):
            parts.append(f"Brand colours: {brief['brand_colours']}")
        if brief.get("campaign_objective"):
            parts.append(f"Objective: {brief['campaign_objective']}")
        if brief.get("restrictions_dont"):
            parts.append(f"Restrictions: {brief['restrictions_dont']}")

        # List available assets
        asset_types = [
            a.get("identified_type", "unknown")
            for a in assets
            if a.get("usable")
        ]
        if asset_types:
            parts.append(f"\nAvailable assets: {', '.join(asset_types)}")

        has_hero = any(
            a.get("identified_type") == "hero" and a.get("usable")
            for a in assets
        )
        if not has_hero:
            parts.append(
                "\nNo hero image provided — plan for Flux-generated base image."
            )

        if reference_descriptions:
            parts.append("\nLayout references provided (see images):")
            for desc in reference_descriptions:
                parts.append(f"  - {desc}")
        else:
            parts.append("\nNo layout references — use best practice for platform.")

        return "\n".join(parts)

    def _parse_plan(self, response: str) -> dict[str, Any]:
        """Extract JSON composition plan from Celeste's response.

        Celeste may include rationale text outside the JSON — strip it.
        Falls back to a minimal default plan if parsing fails entirely.
        """
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        # Try to find JSON object in the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # Fallback: minimal plan so Kai can still produce something
        return {
            "layout_type": "centred",
            "canvas_colour": "#FFFFFF",
            "overlay_colour": None,
            "overlay_opacity": 0.0,
            "hero_image": {
                "position": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 0.7},
                "crop_focus": "centre",
                "opacity": 1.0,
            },
            "logo": {
                "position": {"x": 0.8, "y": 0.9},
                "size_proportion": 0.15,
                "anchor": "bottom-right",
            },
            "text_elements": [],
            "design_elements": [],
            "rationale": "Fallback plan — could not parse art direction response",
        }
