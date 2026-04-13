"""Tests for cost tracker — validates token accumulation and ceiling enforcement."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models import Base, Job
from backend.pipeline.cost_tracker import CostTracker
from backend.utils.llm_client import CostCeilingBreached


@pytest.fixture
def db():
    """In-memory database with a pre-created job for cost tests."""

    async def _setup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with session_maker() as session:
            job = Job(id="JOB-test00000001", cost_ceiling_usd=0.10)
            session.add(job)
            await session.commit()

        return session_maker, engine

    return asyncio.run(_setup())


def test_record_updates_job_total(db):
    """Recording a call should increase the job's running cost total."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            tracker = CostTracker(session)
            total = await tracker.record(
                job_id="JOB-test00000001",
                agent_name="priya",
                step="brief_validation",
                model="claude-opus-4-6",
                input_tokens=1000,
                output_tokens=500,
            )
            await session.commit()

            assert total > 0

            job = await session.get(Job, "JOB-test00000001")
            assert job.total_tokens == 1500
            assert job.total_cost_usd > 0

        await engine.dispose()

    asyncio.run(_test())


def test_cost_ceiling_breach(db):
    """Exceeding the cost ceiling should raise CostCeilingBreached."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            tracker = CostTracker(session)

            # This job has a $0.10 ceiling — a large Opus call should breach it
            with pytest.raises(CostCeilingBreached):
                await tracker.record(
                    job_id="JOB-test00000001",
                    agent_name="celeste",
                    step="art_direction",
                    model="claude-opus-4-6",
                    input_tokens=10000,
                    output_tokens=5000,
                )
            await session.commit()

            job = await session.get(Job, "JOB-test00000001")
            assert job.cost_breached is True

        await engine.dispose()

    asyncio.run(_test())


def test_get_summary(db):
    """Summary should return per-agent breakdown with correct totals."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            # Set ceiling high so we don't breach
            job = await session.get(Job, "JOB-test00000001")
            job.cost_ceiling_usd = 100.0
            await session.flush()

            tracker = CostTracker(session)

            await tracker.record(
                job_id="JOB-test00000001",
                agent_name="priya",
                step="validate",
                model="claude-opus-4-6",
                input_tokens=500,
                output_tokens=200,
            )
            await tracker.record(
                job_id="JOB-test00000001",
                agent_name="dana",
                step="qa_check",
                model="claude-sonnet-4-6",
                input_tokens=1000,
                output_tokens=300,
            )
            await session.commit()

            summary = await tracker.get_summary("JOB-test00000001")

            assert "priya" in summary["per_agent"]
            assert "dana" in summary["per_agent"]
            assert summary["total_tokens"] > 0
            assert summary["total_cost_usd"] > 0
            assert summary["per_agent"]["priya"]["calls"] == 1
            assert summary["per_agent"]["dana"]["calls"] == 1

        await engine.dispose()

    asyncio.run(_test())
