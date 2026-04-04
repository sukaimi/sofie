"""
WebSocket Chat Handler
Real-time conversation with Sofie, with pipeline integration.
"""

from __future__ import annotations

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.chat.memory import get_messages, save_message
from backend.chat.sofie_persona import build_system_prompt
from backend.config import settings
from backend.models import Conversation, async_session
from backend.pipeline.brand_memory import query_brand_context
from backend.pipeline.brief_parser import parse_brief
from backend.pipeline.orchestrator import run_pipeline
from backend.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

BRIEF_READY_TAG = "[BRIEF_READY]"


async def _send_json(ws: WebSocket, msg_type: str, **kwargs) -> None:
    """Send a typed JSON message over WebSocket."""
    await ws.send_json({"type": msg_type, **kwargs})


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

    # Load brand context for Sofie's system prompt
    brand_context = ""
    if brand_id:
        brand_context = await query_brand_context(brand_id, "brand overview guidelines")
        if not brand_context:
            brand_md_path = settings.brands_dir / brand_id / "brand.md"
            if brand_md_path.exists():
                brand_context = brand_md_path.read_text()

    system_prompt = build_system_prompt(brand_context)

    try:
        while True:
            # Receive user message
            data = await websocket.receive_json()
            user_content = data.get("content", "").strip()
            if not user_content:
                continue

            # Save user message
            await save_message(conversation_id, "user", user_content)

            # Build message history for LLM
            history = await get_messages(conversation_id)
            llm_messages = [{"role": "system", "content": system_prompt}] + history

            # Send typing indicator
            await _send_json(websocket, "typing", active=True)

            # Get Sofie's response
            response = await chat_completion(llm_messages, temperature=0.7)

            # Check if brief is ready (Sofie signals this with the tag)
            pipeline_triggered = False
            clean_response = response

            if BRIEF_READY_TAG in response:
                clean_response = response.replace(BRIEF_READY_TAG, "").strip()
                pipeline_triggered = True

            # Save and send Sofie's response
            await save_message(conversation_id, "assistant", clean_response)
            await _send_json(
                websocket,
                "message",
                role="assistant",
                content=clean_response,
            )
            await _send_json(websocket, "typing", active=False)

            # If brief is ready, run the pipeline
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


async def _run_pipeline_from_chat(
    websocket: WebSocket,
    conversation_id: str,
    brand_id: str,
    history: list[dict],
) -> None:
    """Extract brief from conversation and run the image generation pipeline."""
    # Parse brief from conversation
    await _send_json(websocket, "status", message="Understanding your brief...")

    brief_result = await parse_brief(history, brand_id=brand_id)

    if not brief_result.complete or not brief_result.brief:
        # Brief incomplete — Sofie should ask more questions
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

    # Run pipeline with progress updates
    async def on_status(msg: str) -> None:
        await _send_json(websocket, "status", message=msg)

    try:
        job = await run_pipeline(
            brief=brief_result.brief,
            conversation_id=conversation_id,
            on_status=on_status,
        )

        if job.status == "review":
            # Image ready — send it to chat
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
