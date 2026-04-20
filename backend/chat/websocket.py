"""WebSocket handler — real-time chat between brand client and Sofie.

Manages conversation state, routes messages through Sofie agent,
triggers pipeline execution, and relays status updates. Each
WebSocket connection maps to one conversation.
"""

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.sofie import SofieAgent
from backend.config import settings
from backend.models import Conversation, Job
from backend.pipeline.orchestrator import PipelineResult, run_pipeline
from backend.schemas import WebSocketMessage


class ConnectionManager:
    """Track active WebSocket connections for message broadcasting.

    Maps conversation_id → WebSocket so status updates from the
    pipeline can be pushed to the correct client.
    """

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, conversation_id: str, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._connections[conversation_id] = websocket

    def disconnect(self, conversation_id: str) -> None:
        """Remove a disconnected client."""
        self._connections.pop(conversation_id, None)

    async def send_message(
        self, conversation_id: str, msg: WebSocketMessage
    ) -> None:
        """Send a typed message to a specific client."""
        ws = self._connections.get(conversation_id)
        if ws:
            await ws.send_json(msg.model_dump())

    async def send_status(
        self, conversation_id: str, status: str, job_id: str = ""
    ) -> None:
        """Send a pipeline status update to the client."""
        msg = WebSocketMessage(
            type="status",
            role="system",
            content=status,
            job_id=job_id,
        )
        await self.send_message(conversation_id, msg)


manager = ConnectionManager()


async def handle_websocket(
    websocket: WebSocket,
    conversation_id: str,
    session: AsyncSession,
) -> None:
    """Main WebSocket handler — routes all client communication.

    Handles greeting, brief upload triggers, chat messages, and
    feedback. Keeps conversation history in SQLite so reconnections
    preserve context.
    """
    await manager.connect(conversation_id, websocket)
    sofie = SofieAgent(session)

    # Load or create conversation
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        conv = Conversation(id=conversation_id)
        session.add(conv)
        await session.flush()

        # Send greeting
        greeting = await sofie.execute(
            _stub_job(), {"action": "greet"}
        )
        await _send_sofie_message(conversation_id, greeting["message"])
        conv.messages.append(
            {"role": "sofie", "content": greeting["message"]}
        )
        await session.flush()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            msg_type = data.get("type", "message")
            content = data.get("content", "")

            # Record user message
            conv.messages = conv.messages + [{"role": "user", "content": content}]
            await session.flush()

            if msg_type == "brief_uploaded":
                await _handle_brief_upload(
                    conv, data, session, sofie, conversation_id
                )
            elif msg_type == "confirmation":
                await _handle_confirmation(
                    conv, content, session, sofie, conversation_id
                )
            elif msg_type == "feedback":
                await _handle_feedback(
                    conv, content, session, sofie, conversation_id
                )
            else:
                await _handle_chat(
                    conv, content, session, sofie, conversation_id
                )

            await session.commit()

    except WebSocketDisconnect:
        manager.disconnect(conversation_id)
    except Exception as exc:
        await manager.send_message(
            conversation_id,
            WebSocketMessage(
                type="error",
                role="system",
                content=f"An error occurred: {exc}",
            ),
        )
        manager.disconnect(conversation_id)


async def _handle_brief_upload(
    conv: Conversation,
    data: dict[str, Any],
    session: AsyncSession,
    sofie: SofieAgent,
    conversation_id: str,
) -> None:
    """Process an uploaded brief — parse and present for confirmation."""
    metadata = data.get("metadata", {})
    docx_path = metadata.get("file_path", "") or data.get("file_path", "")
    if not docx_path:
        await _send_sofie_message(
            conversation_id,
            "I didn't receive a file. Could you try uploading again?",
        )
        return

    await manager.send_status(conversation_id, "parsing_brief")

    # Create a job for this brief
    job = Job()
    session.add(job)
    await session.flush()

    conv.job_id = job.id
    conv.state = "validating"

    # Run pipeline up to brief parsing
    result = await run_pipeline(
        job=job,
        session=session,
        docx_path=Path(docx_path),
        on_status=lambda s: manager.send_status(conversation_id, s, job.id),
        on_message=lambda m: _send_sofie_message(conversation_id, m, job.id),
    )

    # Present extracted fields for confirmation
    confirm_response = await sofie.execute(
        job,
        {
            "action": "confirm_brief",
            "brief_fields": job.brief_json,
            "warnings": [w.get("message", "") for w in result.warnings],
        },
    )
    await _send_sofie_message(
        conversation_id, confirm_response["message"], job.id
    )
    conv.messages = conv.messages + [
        {"role": "sofie", "content": confirm_response["message"]}
    ]
    conv.state = "awaiting_confirmation" if result.status == "awaiting_confirmation" else "validating"


async def _handle_confirmation(
    conv: Conversation,
    content: str,
    session: AsyncSession,
    sofie: SofieAgent,
    conversation_id: str,
) -> None:
    """User confirmed the brief — continue the pipeline."""
    if not conv.job_id:
        await _send_sofie_message(
            conversation_id,
            "I don't have a brief to work with yet. Could you upload one?",
        )
        return

    job = await session.get(Job, conv.job_id)
    if not job:
        return

    await _send_sofie_message(
        conversation_id,
        "Everything looks good. Starting on your visuals now.",
        job.id,
    )
    conv.messages = conv.messages + [
        {"role": "sofie", "content": "Everything looks good. Starting on your visuals now."}
    ]

    # Run the full pipeline
    result = await run_pipeline(
        job=job,
        session=session,
        on_status=lambda s: manager.send_status(conversation_id, s, job.id),
        on_message=lambda m: _send_sofie_message(conversation_id, m, job.id),
    )

    await _handle_pipeline_result(
        conv, result, job, session, sofie, conversation_id
    )


async def _handle_feedback(
    conv: Conversation,
    feedback: str,
    session: AsyncSession,
    sofie: SofieAgent,
    conversation_id: str,
) -> None:
    """Process user feedback on presented output."""
    if not conv.job_id:
        return

    job = await session.get(Job, conv.job_id)
    if not job:
        return

    eval_result = await sofie.execute(
        job,
        {
            "action": "evaluate_feedback",
            "feedback": feedback,
            "messages": conv.messages,
        },
    )

    feedback_type = eval_result.get("type", "ACTIONABLE")

    if feedback_type == "VAGUE":
        msg = eval_result.get("message", "Could you be more specific?")
        await _send_sofie_message(conversation_id, msg, job.id)
        conv.messages = conv.messages + [{"role": "sofie", "content": msg}]
    elif feedback_type == "UNACTIONABLE":
        msg = eval_result.get("message", "Could you use the feedback menu to guide me?")
        await _send_sofie_message(conversation_id, msg, job.id)
        conv.messages = conv.messages + [{"role": "sofie", "content": msg}]
    else:
        # ACTIONABLE or CONTRADICTORY — proceed with revision
        await _send_sofie_message(
            conversation_id,
            "Got it. Making those changes now.",
            job.id,
        )

        result = await run_pipeline(
            job=job,
            session=session,
            on_status=lambda s: manager.send_status(conversation_id, s, job.id),
            on_message=lambda m: _send_sofie_message(conversation_id, m, job.id),
        )

        await _handle_pipeline_result(
            conv, result, job, session, sofie, conversation_id
        )


async def _handle_chat(
    conv: Conversation,
    content: str,
    session: AsyncSession,
    sofie: SofieAgent,
    conversation_id: str,
) -> None:
    """Handle general chat messages.

    If the conversation has a resumable job (e.g. after a font issue or
    blocker was resolved), re-run the pipeline instead of just chatting.
    """
    job = None
    if conv.job_id:
        job = await session.get(Job, conv.job_id)

    # Resume pipeline if job was paused on a recoverable issue
    if job and conv.state == "resumable":
        await _send_sofie_message(
            conversation_id,
            "Got it — let me pick up where I left off.",
            job.id,
        )
        conv.messages = conv.messages + [
            {"role": "sofie", "content": "Got it — let me pick up where I left off."}
        ]
        conv.state = "processing"

        result = await run_pipeline(
            job=job,
            session=session,
            on_status=lambda s: manager.send_status(conversation_id, s, job.id),
            on_message=lambda m: _send_sofie_message(conversation_id, m, job.id),
        )

        await _handle_pipeline_result(
            conv, result, job, session, sofie, conversation_id
        )
        return

    response = await sofie.execute(
        job or _stub_job(),
        {
            "action": "chat",
            "user_message": content,
            "messages": conv.messages,
        },
    )

    msg = response.get("message", "")
    await _send_sofie_message(conversation_id, msg, conv.job_id or "")
    conv.messages = conv.messages + [{"role": "sofie", "content": msg}]


async def _handle_pipeline_result(
    conv: Conversation,
    result: PipelineResult,
    job: Job,
    session: AsyncSession,
    sofie: SofieAgent,
    conversation_id: str,
) -> None:
    """Route pipeline results to the appropriate Sofie response."""
    if result.status == "blocked":
        resp = await sofie.execute(
            job, {"action": "report_blockers", "blockers": result.blockers}
        )
        await _send_sofie_message(conversation_id, resp["message"], job.id)
        conv.messages = conv.messages + [{"role": "sofie", "content": resp["message"]}]
        conv.state = "resumable"

    elif result.status == "asset_blocked":
        resp = await sofie.execute(
            job, {"action": "report_asset_issues", "blockers": result.blockers}
        )
        await _send_sofie_message(conversation_id, resp["message"], job.id)
        conv.messages = conv.messages + [{"role": "sofie", "content": resp["message"]}]
        conv.state = "resumable"

    elif result.status == "font_issue":
        resp = sofie._report_font_issues({"font_issues": result.font_issues})
        await _send_sofie_message(conversation_id, resp["message"], job.id)
        conv.messages = conv.messages + [{"role": "sofie", "content": resp["message"]}]
        conv.state = "resumable"

    elif result.status in ("review", "review_with_suggestions"):
        # Present output to user
        plan = job.composition_plan or {}
        resp = await sofie.execute(
            job,
            {
                "action": "present_output",
                "rationale": plan.get("rationale", ""),
                "size": job.primary_size,
                "messages": conv.messages,
            },
        )
        msg = resp["message"]

        # Include image paths as metadata
        await manager.send_message(
            conversation_id,
            WebSocketMessage(
                type="image",
                role="sofie",
                content=msg,
                job_id=job.id,
                metadata={"output_paths": result.output_paths},
            ),
        )
        conv.messages = conv.messages + [{"role": "sofie", "content": msg}]

        # If QA had issues, show suggestions for improvement
        if result.status == "review_with_suggestions" and result.qa_results:
            suggestions = _extract_qa_suggestions(result.qa_results)
            if suggestions:
                suggestion_resp = await sofie.execute(
                    job,
                    {
                        "action": "suggest_adjustments",
                        "qa_issues": suggestions,
                        "messages": conv.messages,
                    },
                )
                suggestion_msg = suggestion_resp["message"]
                await _send_sofie_message(
                    conversation_id, suggestion_msg, job.id
                )
                conv.messages = conv.messages + [
                    {"role": "sofie", "content": suggestion_msg}
                ]

        conv.state = "awaiting_feedback"

    elif result.status in ("cost_ceiling_breached", "failed"):
        resp = sofie._escalate({"reason": result.error or result.status})
        await _send_sofie_message(conversation_id, resp["message"], job.id)
        conv.messages = conv.messages + [{"role": "sofie", "content": resp["message"]}]
        conv.state = "resumable"


def _extract_qa_suggestions(qa_results: dict) -> list[str]:
    """Pull specific issues from Dana's QA results for Sofie to suggest fixes."""
    issues = []
    for check_key in ("check1_layout", "check2_brief", "check3_spec"):
        check = qa_results.get(check_key, {})
        if not check.get("pass"):
            issues.extend(check.get("issues", []))
    if qa_results.get("revision_notes"):
        issues.append(qa_results["revision_notes"])
    return issues


async def _send_sofie_message(
    conversation_id: str, content: str, job_id: str = ""
) -> None:
    """Send a standard Sofie chat message."""
    await manager.send_message(
        conversation_id,
        WebSocketMessage(
            type="message",
            role="sofie",
            content=content,
            job_id=job_id,
        ),
    )


def _stub_job() -> Job:
    """Create a temporary Job for pre-pipeline Sofie calls.

    Before a brief is uploaded, Sofie still needs a Job object to
    satisfy the BaseAgent interface. This stub is never persisted.
    """
    return Job(id="STUB-000000000000")
