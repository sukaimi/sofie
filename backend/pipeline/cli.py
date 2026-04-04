"""
CLI test runner for the pipeline.
Usage: python -m backend.pipeline.cli --brand example-brand --brief "Create an Instagram post for Hari Raya"
"""

import argparse
import asyncio
import logging

from backend.models import init_db
from backend.pipeline.orchestrator import run_pipeline
from backend.schemas import BriefSchema, TextOverlay

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def _status_callback(msg: str) -> None:
    print(f"  >> {msg}")


async def main(brand: str, brief_text: str) -> None:
    await init_db()

    brief = BriefSchema(
        brand=brand,
        platform="instagram",
        dimensions="1080x1080",
        campaign="CLI Test",
        key_message=brief_text,
        tone="warm, celebratory",
        must_include=["logo"],
        must_avoid=[],
        text_overlays=[
            TextOverlay(text="Selamat Hari Raya", position="top-centre", style="headline"),
            TextOverlay(text="From our family to yours", position="bottom-centre", style="subhead"),
        ],
    )

    print(f"\nRunning pipeline for brand '{brand}'...")
    job = await run_pipeline(
        brief=brief,
        conversation_id="cli-test",
        on_status=_status_callback,
    )

    print(f"\nJob ID: {job.id}")
    print(f"Status: {job.status}")
    print(f"Output: {job.output_path}")
    print(f"Compliance: {job.compliance_score}/10")
    if job.compliance_notes:
        print(f"Notes: {job.compliance_notes}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SOFIE Pipeline CLI")
    parser.add_argument("--brand", required=True, help="Brand name (directory under brands/)")
    parser.add_argument("--brief", required=True, help="Brief description text")
    args = parser.parse_args()

    asyncio.run(main(args.brand, args.brief))
