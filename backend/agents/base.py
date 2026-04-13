"""Base agent class — standard interface all SOFIE agents implement.

Every agent follows the same pattern: receive input dict from the
orchestrator, execute a task, log token usage, return output dict.
This base class handles the boilerplate so agents only define their
specific logic.
"""

import time
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AgentLog, Job
from backend.pipeline.cost_tracker import CostTracker
from backend.utils.llm_client import LLMClient


class AgentError(Exception):
    """Raised when an agent fails in a way the orchestrator should handle.

    Carries the agent name and step so the orchestrator can log context
    and decide whether to retry or escalate.
    """

    def __init__(self, agent_name: str, step: str, reason: str) -> None:
        self.agent_name = agent_name
        self.step = step
        self.reason = reason
        super().__init__(f"[{agent_name}] {step}: {reason}")


class BaseAgent:
    """Standard interface for all pipeline agents.

    Subclasses must set name, model, and system_prompt, then implement
    execute() with their specific logic. The run() method wraps execute()
    with timing, cost tracking, and error logging.
    """

    name: str = ""
    model: str = ""
    system_prompt: str = ""

    def __init__(self, session: AsyncSession) -> None:
        """Bind agent to a database session for state persistence."""
        self._session = session
        self._llm = LLMClient()
        self._cost_tracker = CostTracker(session)

    async def run(
        self,
        job: Job,
        input_data: dict[str, Any],
        on_status: Callable[[str], Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the agent's task with timing and cost tracking.

        Wraps the subclass execute() method so every agent gets
        consistent logging without reimplementing boilerplate.
        """
        start_ms = time.monotonic()

        if on_status:
            await on_status(f"{self.name}: starting")

        try:
            result = await self.execute(job, input_data)
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(self.name, "execute", str(exc)) from exc

        duration_ms = int((time.monotonic() - start_ms) * 1000)

        # Log completion — token usage is tracked per-call inside execute
        log = AgentLog(
            job_id=job.id,
            agent_name=self.name,
            step=self._get_step_name(),
            status="completed",
            duration_ms=duration_ms,
        )
        self._session.add(log)
        await self._session.flush()

        if on_status:
            await on_status(f"{self.name}: completed")

        return result

    async def execute(
        self, job: Job, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Subclasses implement their specific logic here.

        Must return an output dict. Should use self._llm for LLM calls
        and self._cost_tracker.record() after each call.
        """
        raise NotImplementedError

    async def _call_llm(
        self,
        job: Job,
        messages: list[dict],
        step: str,
        max_tokens: int = 2048,
        images: list[bytes] | None = None,
        model_override: str | None = None,
    ) -> str:
        """Convenience wrapper: make an LLM call and auto-track cost.

        Agents call this instead of self._llm.complete() directly so
        cost tracking is never forgotten.
        """
        model = model_override or self.model

        # Sanitize roles — Anthropic API only accepts "user" and "assistant".
        # Conversation history stores "sofie" and "system" which must be mapped.
        messages = _sanitize_roles(messages)

        response_text, input_tokens, output_tokens, cost_usd = (
            await self._llm.complete(
                model=model,
                messages=messages,
                system=self.system_prompt,
                max_tokens=max_tokens,
                images=images,
                job_id=job.id,
                agent_name=self.name,
            )
        )

        await self._cost_tracker.record(
            job_id=job.id,
            agent_name=self.name,
            step=step,
            model=self._llm.resolve_model(model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return response_text

    def _get_step_name(self) -> str:
        """Default step name derived from agent name.

        Subclasses can override if they perform multiple distinct steps.
        """
        return self.name.lower()


def _sanitize_roles(messages: list[dict]) -> list[dict]:
    """Map conversation roles to Anthropic API roles.

    The chat stores 'sofie' and 'system' roles but Claude's API
    only accepts 'user' and 'assistant'. This prevents 400 errors.
    """
    role_map = {"sofie": "assistant", "system": "user"}
    sanitized = []
    for msg in messages:
        clean = msg.copy()
        clean["role"] = role_map.get(clean.get("role", ""), clean.get("role", "user"))
        sanitized.append(clean)
    return sanitized
