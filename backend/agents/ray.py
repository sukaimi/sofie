"""Ray — Asset Manager agent.

Fetches all asset links from the brief, validates accessibility, uses
vision to identify asset types and assess quality. Reports BLOCKER/WARNING
per asset with platform-specific fix advice.
"""

import json
from typing import Any

from backend.agents.base import BaseAgent
from backend.models import Job
from backend.schemas import AssetResult
from backend.utils.asset_fetcher import fetch_asset


class RayAgent(BaseAgent):
    """Asset manager — downloads, identifies, and validates every asset.

    Ray doesn't trust filenames. He downloads each file, checks magic
    bytes for format, then uses vision to confirm what the asset actually
    is (logo vs hero vs design element). Practical, no philosophy.
    """

    name = "ray"
    model = "sonnet"
    system_prompt = (
        "You are Ray, a studio asset manager.\n\n"
        "You receive an image and must identify what it is:\n"
        "- logo: brand mark or wordmark, usually isolated on transparent bg\n"
        "- hero: lifestyle, product, or campaign photography\n"
        "- element: pattern, texture, frame, graphic device\n"
        "- reference: any image provided as a composition reference\n"
        "- unknown: cannot determine type\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"identified_type": "logo|hero|element|reference|unknown", '
        '"confidence": 0.0-1.0, '
        '"description": "brief description of what you see"}\n\n'
        "Do not trust filenames. Trust the content."
    )

    async def execute(
        self, job: Job, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Fetch and validate all asset links from the brief.

        Two passes: first fetch everything (network-bound), then run
        vision identification on image assets (LLM-bound). This order
        avoids wasting vision tokens on assets that can't be downloaded.
        """
        asset_links = input_data.get("asset_links", {})
        on_status = input_data.get("on_status")
        results: list[dict[str, Any]] = []
        has_blockers = False
        missing_required: list[str] = []

        # Pass 1: fetch and validate all links
        for asset_type, urls in asset_links.items():
            if isinstance(urls, str):
                urls = [urls]

            for url in urls:
                if not url or not url.strip():
                    continue

                # Send live status with filename from URL
                if on_status:
                    filename = url.strip().split("/")[-1].split("?")[0][:40] or asset_type
                    await on_status(f"Downloading {asset_type}: {filename}")

                result = await fetch_asset(url.strip(), asset_type)

                # Pass 2: vision identification for downloaded images
                if result.usable and result.format in ("png", "jpg", "jpeg"):
                    await self._vision_identify(job, result)

                results.append(result.model_dump())

                if result.classification == "BLOCKER":
                    has_blockers = True

        # Check for required assets that weren't provided at all
        # Font is optional — pipeline falls back to DejaVuSans
        if "logo" not in asset_links and "logo_link" not in asset_links:
            missing_required.append("logo")
            has_blockers = True

        return {
            "assets": results,
            "has_blockers": has_blockers,
            "missing_required": missing_required,
            "summary": self._build_summary(results, missing_required),
        }

    async def _vision_identify(
        self, job: Job, result: AssetResult
    ) -> None:
        """Use Claude vision to confirm what an asset actually is.

        Overrides the expected_type if vision disagrees — a file
        labelled 'hero' might actually be a logo, and we need to
        know before composition.
        """
        if not result.local_path:
            return

        try:
            with open(result.local_path, "rb") as f:
                image_bytes = f.read()
        except OSError:
            return

        messages = [
            {
                "role": "user",
                "content": (
                    f"Identify this asset. It was submitted as '{result.identified_type}'. "
                    "Confirm or correct the type."
                ),
            }
        ]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="asset_identification",
            max_tokens=256,
            images=[image_bytes],
        )

        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            vision_result = json.loads(text)
            identified = vision_result.get("identified_type", result.identified_type)
            if identified in ("logo", "hero", "element", "reference", "unknown"):
                result.identified_type = identified
        except (json.JSONDecodeError, KeyError):
            pass

    def _build_summary(
        self,
        results: list[dict[str, Any]],
        missing_required: list[str],
    ) -> str:
        """Human-readable summary for Sofie to relay to the user.

        Counts OK/WARNING/BLOCKER assets so Sofie can give a quick
        status update without dumping raw JSON into chat.
        """
        ok = sum(1 for r in results if r.get("classification") == "OK")
        warnings = sum(1 for r in results if r.get("classification") == "WARNING")
        blockers = sum(1 for r in results if r.get("classification") == "BLOCKER")

        parts = [f"{ok} assets OK"]
        if warnings:
            parts.append(f"{warnings} with warnings")
        if blockers:
            parts.append(f"{blockers} blockers")
        if missing_required:
            parts.append(f"missing required: {', '.join(missing_required)}")

        return "; ".join(parts)
