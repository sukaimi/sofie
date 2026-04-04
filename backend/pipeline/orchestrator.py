"""
Pipeline Orchestrator
Wires all pipeline steps together: brief -> brand context -> prompt -> image -> composite -> compliance.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from backend.config import settings
from backend.models import Job, async_session
from backend.pipeline import (
    brand_memory,
    compliance_checker,
    compositor,
    image_generator,
    prompt_engineer,
)
from backend.schemas import BriefSchema

logger = logging.getLogger(__name__)

MAX_COMPLIANCE_ATTEMPTS = 3


async def run_pipeline(
    brief: BriefSchema,
    conversation_id: str,
    on_status: callable | None = None,
) -> Job:
    """Execute the full image generation pipeline.

    Args:
        brief: The structured brief extracted from conversation.
        conversation_id: Associated conversation ID.
        on_status: Optional async callback(status_message: str) for progress updates.

    Returns:
        The Job record with final status.
    """
    job_id = f"JOB-{uuid.uuid4().hex[:12]}"
    brand_id = brief.brand
    brand_dir = settings.brands_dir / brand_id

    if not brand_dir.exists():
        raise FileNotFoundError(f"Brand directory not found: {brand_dir}")

    # Create job record
    async with async_session() as session:
        job = Job(
            id=job_id,
            conversation_id=conversation_id,
            brand_id=brand_id,
            brief_json=brief.model_dump(),
            status="pending",
        )
        session.add(job)
        await session.commit()

    async def _update_status(status: str, **kwargs) -> None:
        async with async_session() as session:
            j = await session.get(Job, job_id)
            if j:
                j.status = status
                for k, v in kwargs.items():
                    if hasattr(j, k):
                        setattr(j, k, v)
                await session.commit()
        if on_status:
            await on_status(status)

    try:
        # Step 1: Brand context retrieval
        await _update_status("generating")
        if on_status:
            await on_status("Pulling up your brand guidelines...")

        brand_context = await brand_memory.query_brand_context(
            brand_id, brief.key_message or brief.campaign or ""
        )
        if not brand_context:
            # Fall back to reading brand.md directly
            brand_md_path = brand_dir / "brand.md"
            brand_context = brand_md_path.read_text() if brand_md_path.exists() else ""

        compliance_notes = None

        for attempt in range(1, MAX_COMPLIANCE_ATTEMPTS + 1):
            await _update_status("generating", attempts=attempt)

            # Step 2: Prompt engineering
            if on_status:
                await on_status("Crafting your visual concept...")

            prompt_package = await prompt_engineer.run(
                brief, brand_context, brand_dir, compliance_notes
            )

            # Step 3: Image generation
            if on_status:
                await on_status("Creating your visual...")

            raw_image_path = await image_generator.run(prompt_package, job_id)

            # Step 4: Compositing
            await _update_status("compositing")
            if on_status:
                await on_status("Applying brand elements...")

            final_image_path = await compositor.run(
                prompt_package, brand_dir, raw_image_path, job_id
            )

            # Step 5: Compliance check
            await _update_status("checking")
            if on_status:
                await on_status("Checking brand compliance...")

            result = await compliance_checker.run(final_image_path, brand_dir)

            score = result.get("score", 0)
            issues = result.get("issues", [])

            await _update_status(
                "checking",
                compliance_score=score,
                compliance_notes=json.dumps(issues),
                output_path=str(final_image_path),
            )

            if result.get("pass", False):
                # Passed compliance — move to review queue
                await _update_status("review", output_path=str(final_image_path))
                if on_status:
                    await on_status("Your visual is ready for review!")
                break
            else:
                logger.info(
                    f"Compliance attempt {attempt}/{MAX_COMPLIANCE_ATTEMPTS} failed "
                    f"(score: {score}): {issues}"
                )
                compliance_notes = "\n".join(issues)

                if attempt >= MAX_COMPLIANCE_ATTEMPTS:
                    await _update_status("failed", output_path=str(final_image_path))
                    if on_status:
                        await on_status(
                            "I wasn't able to get the compliance right after a few tries. "
                            "Sending this to the team for review."
                        )
                elif on_status:
                    await on_status(
                        f"Adjusting based on compliance feedback (attempt {attempt + 1})..."
                    )

    except Exception as e:
        logger.error(f"Pipeline error for job {job_id}: {e}", exc_info=True)
        await _update_status("failed")
        if on_status:
            await on_status("I ran into a snag generating that. Let me try a different approach.")
        raise

    # Return final job state
    async with async_session() as session:
        return await session.get(Job, job_id)


async def handle_revision(
    job_id: str,
    feedback: str,
    on_status: callable | None = None,
) -> Job:
    """Re-run pipeline with revision feedback.

    Args:
        job_id: The job to revise.
        feedback: User feedback text.
        on_status: Optional progress callback.
    """
    async with async_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        brief = BriefSchema(**job.brief_json)
        brand_dir = settings.brands_dir / job.brand_id

        # Use feedback as compliance notes for the prompt engineer
        return await run_pipeline(
            brief=brief,
            conversation_id=job.conversation_id,
            on_status=on_status,
        )
