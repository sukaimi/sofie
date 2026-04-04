"""
WebSocket Chat Handler
Real-time conversation with Sofie, with pipeline and brand onboarding integration.
"""

from __future__ import annotations

import json
import logging
import re

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.chat.memory import get_messages, save_message
from backend.chat.sofie_persona import build_onboarding_prompt, build_system_prompt
from backend.config import settings
from backend.models import Brand, Conversation, async_session
from backend.pipeline.brand_memory import query_brand_context
from backend.pipeline.brief_parser import parse_brief
from backend.pipeline.orchestrator import run_pipeline
from backend.schemas import BrandOnboardSchema
from backend.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

BRIEF_READY_TAG = "[BRIEF_READY]"
BRAND_READY_TAG = "[BRAND_READY]"


async def _send_json(ws: WebSocket, msg_type: str, **kwargs) -> None:
    await ws.send_json({"type": msg_type, **kwargs})


async def _get_existing_brand_names() -> list[str]:
    async with async_session() as session:
        result = await session.execute(select(Brand.name))
        return [row[0] for row in result.all()]


async def chat_handler(websocket: WebSocket, conversation_id: str) -> None:
    """Handle a WebSocket chat session."""
    await websocket.accept()

    # Load or verify conversation exists
    async with async_session() as session:
        conv = await session.get(Conversation, conversation_id)
        if not conv:
            await _send_json(websocket, "error", message="Conversation not found")
            await websocket.close()
            return
        brand_id = conv.brand_id

    # Determine mode: onboarding (no brand) or image generation (has brand)
    is_onboarding = brand_id is None

    if is_onboarding:
        existing_brands = await _get_existing_brand_names()
        system_prompt = build_onboarding_prompt(existing_brands)
    else:
        brand_context = ""
        brand_context = await query_brand_context(brand_id, "brand overview guidelines")
        if not brand_context:
            brand_md_path = settings.brands_dir / brand_id / "brand.md"
            if brand_md_path.exists():
                brand_context = brand_md_path.read_text()
        system_prompt = build_system_prompt(brand_context)

    try:
        while True:
            data = await websocket.receive_json()
            user_content = data.get("content", "").strip()
            if not user_content:
                continue

            await save_message(conversation_id, "user", user_content)
            history = await get_messages(conversation_id)
            llm_messages = [{"role": "system", "content": system_prompt}] + history

            await _send_json(websocket, "typing", active=True)
            response = await chat_completion(llm_messages, temperature=0.7)

            # Handle brand onboarding completion
            if is_onboarding and BRAND_READY_TAG in response:
                clean_response, brand_json = _extract_brand_json(response)

                await save_message(conversation_id, "assistant", clean_response)
                await _send_json(
                    websocket, "message", role="assistant", content=clean_response
                )
                await _send_json(websocket, "typing", active=False)

                if brand_json:
                    new_brand_id = await _create_brand_from_chat(
                        websocket, conversation_id, brand_json
                    )
                    if new_brand_id:
                        # Switch to image generation mode
                        brand_id = new_brand_id
                        is_onboarding = False
                        brand_context = await query_brand_context(
                            brand_id, "brand overview guidelines"
                        )
                        system_prompt = build_system_prompt(brand_context)

                        # Notify frontend
                        await _send_json(
                            websocket,
                            "brand_created",
                            brand_id=brand_id,
                            brand_name=brand_json.get("name", ""),
                        )
                continue

            # Handle image generation trigger
            pipeline_triggered = False
            clean_response = response

            if BRIEF_READY_TAG in response:
                clean_response = response.replace(BRIEF_READY_TAG, "").strip()
                pipeline_triggered = True

            await save_message(conversation_id, "assistant", clean_response)
            await _send_json(
                websocket, "message", role="assistant", content=clean_response
            )
            await _send_json(websocket, "typing", active=False)

            if pipeline_triggered and brand_id:
                await _run_pipeline_from_chat(
                    websocket, conversation_id, brand_id, history
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await _send_json(websocket, "error", message=str(e))
        except Exception:
            pass


def _extract_brand_json(response: str) -> tuple[str, dict | None]:
    """Extract the [BRAND_READY] tag and JSON from Sofie's response."""
    # Split on the tag
    parts = response.split(BRAND_READY_TAG)
    clean_text = parts[0].strip()

    if len(parts) < 2:
        return clean_text, None

    json_text = parts[1].strip()
    # Strip markdown fences
    json_text = re.sub(r"^```(?:json)?\s*\n?", "", json_text)
    json_text = re.sub(r"\n?```\s*$", "", json_text)

    try:
        return clean_text, json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse brand JSON: {e}")
        return clean_text, None


async def _create_brand_from_chat(
    websocket: WebSocket,
    conversation_id: str,
    brand_data: dict,
) -> str | None:
    """Create a brand from conversational data."""
    from backend.pipeline.brand_memory import ingest_brand

    try:
        schema = BrandOnboardSchema(**brand_data)
    except Exception as e:
        logger.warning(f"Invalid brand data: {e}")
        msg = "I had trouble saving that brand info. Could you tell me the brand name and colours again?"
        await save_message(conversation_id, "assistant", msg)
        await _send_json(websocket, "message", role="assistant", content=msg)
        return None

    brand_id = schema.name.lower().replace(" ", "-").replace("'", "")

    await _send_json(websocket, "status", message="Setting up your brand...")

    # Create brand directory and markdown
    brand_dir = settings.brands_dir / brand_id
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (brand_dir / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    (brand_dir / "assets" / "elements").mkdir(parents=True, exist_ok=True)

    colours_section = "\n".join(
        f"- **{c.get('name', 'Color')}:** {c.get('hex', '#000000')}"
        for c in schema.colours
    ) if schema.colours else "- Not specified"

    dos_section = "\n".join(f"- {d}" for d in schema.dos) if schema.dos else "- Not specified"
    donts_section = "\n".join(f"- {d}" for d in schema.donts) if schema.donts else "- Not specified"

    brand_md = f"""# {schema.name} — Brand Guidelines

## Brand Name
{schema.name}

## Tagline
{f'"{schema.tagline}"' if schema.tagline else 'Not specified'}

## Brand Summary
{schema.summary}

## Colour Palette
{colours_section}

## Typography
{schema.typography or 'Not specified'}

## Tone of Voice
{schema.tone or 'Not specified'}

## Target Audience
{schema.target_audience or 'Not specified'}

## Do's
{dos_section}

## Don'ts
{donts_section}
"""

    (brand_dir / "brand.md").write_text(brand_md, encoding="utf-8")

    # Ingest into ChromaDB
    await ingest_brand(brand_id, brand_dir)

    # Create DB record
    async with async_session() as session:
        brand = Brand(
            id=brand_id,
            name=schema.name,
            summary_path=str(brand_dir / "brand.md"),
            assets_path=str(brand_dir / "assets"),
        )
        session.add(brand)
        await session.commit()

        # Update conversation's brand_id
        conv = await session.get(Conversation, conversation_id)
        if conv:
            conv.brand_id = brand_id
            await session.commit()

    logger.info(f"Brand created via chat: {schema.name} ({brand_id})")

    confirm_msg = (
        f"Your brand **{schema.name}** is all set up! "
        f"I've saved your guidelines and I'm ready to create visuals for you. "
        f"What would you like to make?"
    )
    await save_message(conversation_id, "assistant", confirm_msg)
    await _send_json(websocket, "message", role="assistant", content=confirm_msg)

    return brand_id


async def _run_pipeline_from_chat(
    websocket: WebSocket,
    conversation_id: str,
    brand_id: str,
    history: list[dict],
) -> None:
    """Extract brief from conversation and run the image generation pipeline."""
    await _send_json(websocket, "status", message="Understanding your brief...")

    brief_result = await parse_brief(history, brand_id=brand_id)

    if not brief_result.complete or not brief_result.brief:
        if brief_result.follow_up_question:
            await save_message(
                conversation_id, "assistant", brief_result.follow_up_question
            )
            await _send_json(
                websocket,
                "message",
                role="assistant",
                content=brief_result.follow_up_question,
            )
        return

    async def on_status(msg: str) -> None:
        await _send_json(websocket, "status", message=msg)

    try:
        job = await run_pipeline(
            brief=brief_result.brief,
            conversation_id=conversation_id,
            on_status=on_status,
        )

        if job.status == "review":
            image_url = f"/api/images/{job.id}/final"
            rationale = (
                f"Here's your {brief_result.brief.campaign or 'visual'} — "
                f"I matched the {brief_result.brief.tone or 'requested'} tone "
                f"with your brand colours."
            )
            await save_message(conversation_id, "assistant", rationale)
            await _send_json(
                websocket,
                "image",
                job_id=job.id,
                image_url=image_url,
                caption=rationale,
            )
        elif job.status == "failed":
            fail_msg = (
                "I had some trouble getting the compliance just right. "
                "I've sent it to the team for a closer look."
            )
            await save_message(conversation_id, "assistant", fail_msg)
            await _send_json(
                websocket, "message", role="assistant", content=fail_msg
            )

    except Exception as e:
        logger.error(f"Pipeline error in chat: {e}", exc_info=True)
        error_msg = "I ran into a snag generating that. Could you try describing what you need again?"
        await save_message(conversation_id, "assistant", error_msg)
        await _send_json(
            websocket, "message", role="assistant", content=error_msg
        )
