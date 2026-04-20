"""Ray — Asset Manager agent.

Fetches all asset links from the brief, validates accessibility, uses
vision to identify asset types and assess quality. Reports BLOCKER/WARNING
per asset with platform-specific fix advice.
"""

import json
from typing import Any

from backend.agents.base import BaseAgent
from backend.config import settings
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
        import asyncio

        asset_links = input_data.get("asset_links", {})
        on_status = input_data.get("on_status")
        has_blockers = False
        missing_required: list[str] = []

        # Build flat list of (url, asset_type) pairs
        fetch_tasks: list[tuple[str, str]] = []
        for asset_type, urls in asset_links.items():
            if isinstance(urls, str):
                urls = [urls]
            for url in urls:
                if url and url.strip():
                    fetch_tasks.append((url.strip(), asset_type))

        # Pass 1: fetch all assets in parallel
        async def _fetch_one(url: str, asset_type: str) -> AssetResult:
            if on_status:
                filename = url.split("/")[-1].split("?")[0][:40] or asset_type
                await on_status(f"Downloading {asset_type}: {filename}")
            return await fetch_asset(url, asset_type)

        fetched = await asyncio.gather(
            *[_fetch_one(url, at) for url, at in fetch_tasks]
        )

        # Pass 2: vision identification + PDF brand extraction
        results: list[dict[str, Any]] = []
        brand_context: dict[str, Any] = {}
        for result in fetched:
            # If it's a PDF, treat it as brand guidelines + extract embedded images
            if result.local_path and result.format in ("unknown", "pdf"):
                try:
                    with open(result.local_path, "rb") as f:
                        header = f.read(5)
                    if header == b"%PDF-":
                        if on_status:
                            await on_status("Reading brand guidelines PDF")
                        brand_context = await self._extract_brand_from_pdf(
                            job, result.local_path
                        )
                        result.classification = "OK"
                        result.usable = True
                        result.identified_type = "brand_guidelines"
                        result.issues = []

                        # Extract embedded images (logos, etc.)
                        if on_status:
                            await on_status("Extracting images from PDF")
                        pdf_images = await self._extract_and_identify_pdf_images(
                            job, result.local_path, on_status
                        )
                        # If no embedded images found, render pages as images
                        if not pdf_images:
                            if on_status:
                                await on_status("Rendering PDF pages as images")
                            pdf_images = await self._render_pdf_pages_as_assets(
                                job, result.local_path, on_status
                            )
                        results.extend(pdf_images)
                except OSError:
                    pass
            elif result.usable and result.format in ("png", "jpg", "jpeg"):
                if on_status:
                    filename = (result.local_path or "").split("/")[-1] or "image"
                    await on_status(f"Identifying asset: {filename}")
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
            "brand_context": brand_context,
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

    async def _extract_and_identify_pdf_images(
        self, job: Job, pdf_path: str, on_status: Any = None
    ) -> list[dict[str, Any]]:
        """Extract embedded images from a PDF and identify them via vision.

        Saves each extracted image to temp, runs vision identification,
        and returns them as asset result dicts ready to merge into results.
        """
        from backend.utils.pdf_brand_extractor import extract_images_from_pdf

        try:
            pdf_images = extract_images_from_pdf(pdf_path, min_size=100, max_images=5)
        except Exception:
            return []

        extracted_results = []
        for i, img_data in enumerate(pdf_images):
            # Save to temp
            temp_path = settings.temp_dir / f"pdf_extract_{i}_{hash(pdf_path) % 10**8}.png"
            temp_path.write_bytes(img_data["bytes"])

            # Create a result entry
            from backend.schemas import AssetResult
            result = AssetResult(
                url=f"extracted_from_pdf_page_{img_data['page']}",
                identified_type="unknown",
                local_path=str(temp_path),
                format="png",
                dimensions=(img_data["width"], img_data["height"]),
                usable=True,
                classification="OK",
            )

            # Vision identify
            if on_status:
                await on_status(f"Identifying extracted image {i+1} from PDF")
            await self._vision_identify(job, result)

            extracted_results.append(result.model_dump())

        return extracted_results

    async def _render_pdf_pages_as_assets(
        self, job: Job, pdf_path: str, on_status: Any = None
    ) -> list[dict[str, Any]]:
        """Render PDF pages as images and identify them via vision.

        Fallback when no embedded raster images exist — the logo might
        be vector art drawn directly in the PDF.
        """
        from backend.utils.pdf_brand_extractor import pdf_to_page_images

        try:
            page_images = pdf_to_page_images(pdf_path, max_pages=3, dpi=200)
        except Exception:
            return []

        extracted_results = []
        for i, img_bytes in enumerate(page_images):
            temp_path = settings.temp_dir / f"pdf_page_{i}_{hash(pdf_path) % 10**8}.png"
            temp_path.write_bytes(img_bytes)

            result = AssetResult(
                url=f"rendered_pdf_page_{i}",
                identified_type="unknown",
                local_path=str(temp_path),
                format="png",
                usable=True,
                classification="OK",
            )

            if on_status:
                await on_status(f"Identifying PDF page {i+1}")
            await self._vision_identify(job, result)

            extracted_results.append(result.model_dump())

        return extracted_results

    async def _extract_brand_from_pdf(
        self, job: Job, pdf_path: str
    ) -> dict[str, Any]:
        """Read a brand guidelines PDF and extract brand elements via vision.

        Sends up to 6 pages as images to Claude vision with a structured
        extraction prompt. Returns brand context dict.
        """
        from backend.utils.pdf_brand_extractor import (
            BRAND_EXTRACTION_PROMPT,
            pdf_to_page_images,
        )

        try:
            page_images = pdf_to_page_images(pdf_path, max_pages=6)
        except Exception:
            return {}

        if not page_images:
            return {}

        messages = [{"role": "user", "content": BRAND_EXTRACTION_PROMPT}]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="brand_pdf_extraction",
            max_tokens=1024,
            images=page_images,
        )

        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, KeyError):
            pass

        return {}

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
