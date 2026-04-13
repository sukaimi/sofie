"""Pipeline orchestrator — wires all agents together with retry logic.

Follows the pipeline sequence from TDD section 6: Marcus → Priya → font
check → Ray → Celeste → QA loop (Kai → Dana, max 3) → present to user.
Failed jobs are resumable from the last successful step.
"""

from pathlib import Path
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.celeste import CelesteAgent
from backend.agents.dana import DanaAgent
from backend.agents.marcus import MarcusAgent
from backend.agents.priya import PriyaAgent
from backend.agents.ray import RayAgent
from backend.config import settings
from backend.models import Job
from backend.pipeline.brief_parser import parse_brief
from backend.utils.compositor import composite
from backend.utils.file_server import get_output_path
from backend.utils.image_gen_client import generate_image
from backend.utils.llm_client import CostCeilingBreached
from backend.utils.text_renderer import check_font_coverage, render_text_layer


class PipelineResult:
    """Outcome of a pipeline run — carries state for the WebSocket layer.

    Separates 'what happened' from 'what to do next' so the chat layer
    can decide how to present results to the user.
    """

    def __init__(
        self,
        job_id: str,
        status: str,
        output_paths: dict[str, str] | None = None,
        blockers: list[dict[str, str]] | None = None,
        warnings: list[dict[str, str]] | None = None,
        font_issues: list[str] | None = None,
        qa_results: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.job_id = job_id
        self.status = status
        self.output_paths = output_paths or {}
        self.blockers = blockers or []
        self.warnings = warnings or []
        self.font_issues = font_issues or []
        self.qa_results = qa_results
        self.error = error


async def run_pipeline(
    job: Job,
    session: AsyncSession,
    docx_path: Path | None = None,
    on_status: Callable[[str], Any] | None = None,
) -> PipelineResult:
    """Execute the full production pipeline for a single job.

    Follows CLAUDE.md build order: parse → validate → assets → art
    direction → compose → QA loop. Each step writes to job state
    so failures can resume from the last checkpoint.
    """
    marcus = MarcusAgent(session)
    priya = PriyaAgent(session)
    ray = RayAgent(session)
    celeste = CelesteAgent(session)
    dana = DanaAgent(session)

    try:
        # Step 1: Parse brief (if docx provided)
        if docx_path and not job.brief_json:
            if on_status:
                await on_status("parsing_brief")
            brief_result = await parse_brief(docx_path)
            job.brief_json = brief_result.fields
            job.brand_name = brief_result.fields.get("brand_name", "")
            job.job_title = brief_result.fields.get("job_title", "")
            sizes = brief_result.fields.get("output_sizes", [])
            if isinstance(sizes, str):
                sizes = [s.strip() for s in sizes.split(",")]
            job.output_sizes = sizes
            await session.flush()

            # Return early for user confirmation of extracted fields
            return PipelineResult(
                job_id=job.id,
                status="awaiting_confirmation",
                warnings=[{"field": w, "message": w} for w in brief_result.warnings],
            )

        brief = job.brief_json
        await marcus.run(job, {"action": "update_status", "new_status": "validating"})

        # Step 2: Validate brief (Priya)
        if on_status:
            await on_status("validating_brief")
        validation = await priya.run(job, {"brief_fields": brief})
        if validation.get("has_blockers"):
            return PipelineResult(
                job_id=job.id,
                status="blocked",
                blockers=validation["blockers"],
                warnings=validation.get("warnings", []),
            )

        # Step 3: Font check
        if on_status:
            await on_status("font_check")
        font_path_str = brief.get("brand_font_link", "")
        texts_to_check = [
            brief.get("headline_text", ""),
            brief.get("sub_copy", ""),
            brief.get("cta_text", ""),
            brief.get("mandatory_inclusions", ""),
        ]
        texts_to_check = [t for t in texts_to_check if t]

        font_issues: list[str] = []
        if font_path_str and texts_to_check:
            font_issues = check_font_coverage(Path(font_path_str), texts_to_check)
            if font_issues:
                return PipelineResult(
                    job_id=job.id,
                    status="font_issue",
                    font_issues=font_issues,
                )

        # Step 4: Fetch and validate assets (Ray)
        if on_status:
            await on_status("validating_assets")
        asset_links = _extract_asset_links(brief)
        asset_result = await ray.run(job, {"asset_links": asset_links})
        if asset_result.get("has_blockers"):
            return PipelineResult(
                job_id=job.id,
                status="asset_blocked",
                blockers=[
                    {"field": a.get("url", ""), "message": "; ".join(a.get("issues", []))}
                    for a in asset_result.get("assets", [])
                    if a.get("classification") == "BLOCKER"
                ],
            )

        job.asset_manifest = asset_result
        await session.flush()

        # Build asset path lookup for compositor
        asset_paths = _build_asset_paths(asset_result.get("assets", []))

        # Determine primary size
        sizes = job.output_sizes or ["1080x1080"]
        primary_size = sizes[0]
        job.primary_size = primary_size
        await session.flush()

        await marcus.run(job, {"action": "update_status", "new_status": "compositing"})

        # Step 5: Art direction (Celeste)
        if on_status:
            await on_status("art_direction")
        plan = await celeste.run(
            job,
            {
                "brief_fields": brief,
                "assets": asset_result.get("assets", []),
                "dimensions": primary_size,
            },
        )

        # Generate hero image if none provided
        if not asset_paths.get("hero"):
            if on_status:
                await on_status("generating_hero")
            w, h = _parse_dimensions(primary_size)
            hero_prompt = _build_hero_prompt(brief, plan)
            hero_path = await generate_image(hero_prompt, (w, h), job.id)
            if hero_path:
                asset_paths["hero"] = str(hero_path)

        # QA loop (max 3 attempts per CLAUDE.md)
        output_paths: dict[str, str] = {}

        for size in sizes:
            w, h = _parse_dimensions(size)
            output_path = get_output_path(job.id, size)

            for attempt in range(1, settings.max_qa_attempts + 1):
                if on_status:
                    await on_status(f"compositing_{size}_attempt_{attempt}")

                # Step 6: Composite (Kai)
                composite(plan, asset_paths, output_path, (w, h), settings.jpg_quality)

                # Apply text layers via Cairo
                if plan.get("text_elements"):
                    from PIL import Image
                    base = Image.open(output_path)
                    font_p = _resolve_font_path(asset_paths, brief)
                    rendered = render_text_layer(base, plan["text_elements"], font_p)
                    if output_path.suffix.lower() in (".jpg", ".jpeg"):
                        rendered.convert("RGB").save(str(output_path), "JPEG", quality=settings.jpg_quality)
                    else:
                        rendered.save(str(output_path), "PNG")

                await marcus.run(job, {"action": "update_status", "new_status": "qa"})

                # Step 7: QA (Dana)
                if on_status:
                    await on_status(f"qa_check_{size}")
                qa_result = await dana.run(
                    job,
                    {
                        "image_path": str(output_path),
                        "brief_fields": brief,
                        "composition_plan": plan,
                        "dimensions": size,
                    },
                )

                if qa_result.get("overall_pass"):
                    output_paths[size] = str(output_path)
                    break
                elif attempt == settings.max_qa_attempts:
                    # Escalate after max QA attempts
                    qa_increment = await marcus.run(job, {"action": "increment_qa"})
                    if qa_increment.get("escalated"):
                        return PipelineResult(
                            job_id=job.id,
                            status="escalated",
                            qa_results=qa_result,
                            error="QA failed after maximum attempts",
                        )
                else:
                    # Revise plan based on QA feedback
                    issues = []
                    for check_key in ("check1_layout", "check2_brief", "check3_spec"):
                        issues.extend(qa_result.get(check_key, {}).get("issues", []))
                    plan = await celeste.revise_plan(job, issues, plan)
                    await marcus.run(job, {"action": "increment_qa"})

        # Success — update job with output paths
        job.output_paths = output_paths
        job.status = "review"
        await session.flush()

        return PipelineResult(
            job_id=job.id,
            status="review",
            output_paths=output_paths,
            qa_results=qa_result,
        )

    except CostCeilingBreached as exc:
        return PipelineResult(
            job_id=job.id,
            status="cost_ceiling_breached",
            error=str(exc),
        )
    except Exception as exc:
        job.status = "failed"
        job.error_log += f"\n[pipeline_error] {exc}"
        await session.flush()
        return PipelineResult(
            job_id=job.id,
            status="failed",
            error=str(exc),
        )


def _extract_asset_links(brief: dict[str, Any]) -> dict[str, list[str]]:
    """Pull asset URLs from brief fields into a typed dict for Ray.

    Maps brief field names to asset type categories so Ray knows
    what validation rules to apply to each link.
    """
    links: dict[str, list[str]] = {}

    mapping = {
        "logo_link": "logo",
        "brand_font_link": "font",
        "hero_image_links": "hero",
        "design_elements_links": "element",
        "own_past_ad_links": "reference",
        "external_ref_links": "reference",
        "mood_ref_links": "reference",
    }

    for field, asset_type in mapping.items():
        value = brief.get(field)
        if not value:
            continue
        if isinstance(value, str):
            value = [value]
        if asset_type not in links:
            links[asset_type] = []
        links[asset_type].extend(value)

    return links


def _build_asset_paths(assets: list[dict[str, Any]]) -> dict[str, str]:
    """Build a type→path lookup from validated assets for the compositor.

    First usable asset of each type wins — compositor doesn't handle
    multiple logos or heroes (POC limitation).
    """
    paths: dict[str, str] = {}
    element_idx = 0

    for asset in assets:
        if not asset.get("usable") or not asset.get("local_path"):
            continue

        asset_type = asset.get("identified_type", "unknown")
        if asset_type in ("logo", "hero") and asset_type not in paths:
            paths[asset_type] = asset["local_path"]
        elif asset_type == "element":
            paths[f"element_{element_idx}"] = asset["local_path"]
            element_idx += 1
        elif asset_type in ("pattern", "texture") and "pattern" not in paths:
            paths["pattern"] = asset["local_path"]

    return paths


def _parse_dimensions(size_str: str) -> tuple[int, int]:
    """Parse '1080x1080' format to (width, height) tuple."""
    parts = size_str.lower().split("x")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return 1080, 1080


def _resolve_font_path(
    asset_paths: dict[str, str], brief: dict[str, Any]
) -> Path:
    """Find the font file path from assets or brief.

    Falls back to a system font if no brand font is available —
    the composition should still work, just without brand typography.
    """
    font = asset_paths.get("font")
    if font:
        return Path(font)

    brief_font = brief.get("brand_font_link", "")
    if brief_font and Path(brief_font).exists():
        return Path(brief_font)

    return Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _build_hero_prompt(brief: dict[str, Any], plan: dict[str, Any]) -> str:
    """Build a Flux prompt from brief context — no text instructions.

    Per CLAUDE.md: prompts must NOT contain text rendering instructions.
    Focus on visual style, mood, colours, and subject matter.
    """
    parts = []

    objective = brief.get("campaign_objective", "")
    if objective:
        parts.append(f"Campaign: {objective}")

    key_msg = brief.get("key_message", "")
    if key_msg:
        parts.append(f"Mood: {key_msg}")

    colours = brief.get("brand_colours", "")
    if colours:
        parts.append(f"Colour palette: {colours}")

    industry = brief.get("industry", "")
    if industry:
        parts.append(f"Industry: {industry}")

    parts.append("Professional, clean, modern aesthetic. High quality photography style.")

    return ". ".join(parts)
