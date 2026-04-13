"""Per-job token and cost accumulation.

Tracks cumulative LLM spend across all agents for a single job.
Enforces the hard cost ceiling ($2.00 default) — if breached, raises
CostCeilingBreached so the orchestrator can pause and alert the operator.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AgentLog, Job
from backend.utils.llm_client import CostCeilingBreached, _COST_PER_MTK


class CostTracker:
    """Accumulates token usage and cost per job.

    Every agent call flows through record() which updates both the
    AgentLog (audit trail) and the Job (running total). The ceiling
    check happens before returning so the orchestrator can halt
    immediately rather than discovering the breach later.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind to a database session for atomic reads and writes."""
        self._session = session

    async def record(
        self,
        job_id: str,
        agent_name: str,
        step: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int = 0,
        notes: str = "",
    ) -> float:
        """Log an agent call's token usage and update the job total.

        Returns the job's new cumulative cost. Raises CostCeilingBreached
        if the ceiling is exceeded — the orchestrator must catch this
        and pause the job.
        """
        cost_usd = _calculate_call_cost(model, input_tokens, output_tokens)

        # Write audit log entry
        log = AgentLog(
            job_id=job_id,
            agent_name=agent_name,
            step=step,
            status="completed",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            notes=notes,
        )
        self._session.add(log)

        # Update job running totals
        job = await self._session.get(Job, job_id)
        if not job:
            await self._session.flush()
            return cost_usd

        job.total_tokens += input_tokens + output_tokens
        job.total_cost_usd += cost_usd
        await self._session.flush()

        # Check ceiling — operator must explicitly extend if breached
        if job.total_cost_usd >= job.cost_ceiling_usd:
            job.cost_breached = True
            await self._session.flush()
            raise CostCeilingBreached(
                job_id=job_id,
                current_cost=job.total_cost_usd,
                ceiling=job.cost_ceiling_usd,
            )

        return job.total_cost_usd

    async def get_summary(self, job_id: str) -> dict:
        """Return per-agent cost breakdown and job total.

        Used by the operator dashboard to show where money was spent
        and by Sofie to report cost in chat when asked.
        """
        stmt = select(AgentLog).where(AgentLog.job_id == job_id)
        result = await self._session.execute(stmt)
        logs = result.scalars().all()

        per_agent: dict[str, dict[str, float | int]] = {}
        total_cost = 0.0
        total_tokens = 0

        for log in logs:
            if log.agent_name not in per_agent:
                per_agent[log.agent_name] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            entry = per_agent[log.agent_name]
            entry["input_tokens"] += log.input_tokens
            entry["output_tokens"] += log.output_tokens
            entry["cost_usd"] += log.cost_usd
            entry["calls"] += 1
            total_cost += log.cost_usd
            total_tokens += log.input_tokens + log.output_tokens

        return {
            "job_id": job_id,
            "per_agent": per_agent,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
        }


def _calculate_call_cost(
    model: str, input_tokens: int, output_tokens: int
) -> float:
    """Calculate USD cost for a single LLM call.

    Duplicates the logic from llm_client to avoid circular imports —
    the cost table is small and stable enough that this is acceptable.
    """
    rates = _COST_PER_MTK.get(model)
    if not rates:
        return 0.0

    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost
