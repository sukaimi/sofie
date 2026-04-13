"""Tests for SQLAlchemy models — validates schema and defaults."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models import AgentLog, Base, Conversation, Job


@pytest.fixture
def db():
    """In-memory SQLite with tables created."""

    async def _setup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine

    return asyncio.run(_setup())


def test_job_defaults(db):
    """New Job persisted to DB should have correct default values."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            job = Job()
            session.add(job)
            await session.flush()

            assert job.status == "pending"
            assert job.total_cost_usd == 0.0
            assert job.cost_ceiling_usd == 2.00
            assert job.cost_breached is False
            assert job.compliance_attempts == 0
            assert job.user_revision_count == 0
        await engine.dispose()

    asyncio.run(_test())


def test_job_id_format(db):
    """Job ID should start with JOB- prefix after flush."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            job = Job()
            session.add(job)
            await session.flush()

            assert job.id.startswith("JOB-")
            assert len(job.id) == 16
        await engine.dispose()

    asyncio.run(_test())


def test_conversation_id_format(db):
    """Conversation ID should start with CONV- prefix after flush."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            conv = Conversation()
            session.add(conv)
            await session.flush()

            assert conv.id.startswith("CONV-")
        await engine.dispose()

    asyncio.run(_test())


def test_conversation_defaults(db):
    """New Conversation should have greeting state and empty messages."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            conv = Conversation()
            session.add(conv)
            await session.flush()

            assert conv.state == "greeting"
            assert conv.messages == []
            assert conv.job_id is None
        await engine.dispose()

    asyncio.run(_test())


def test_agent_log_defaults(db):
    """New AgentLog should have zero token counts."""
    session_maker, engine = db

    async def _test():
        async with session_maker() as session:
            log = AgentLog(job_id="JOB-000000000000", agent_name="test", step="test")
            session.add(log)
            await session.flush()

            assert log.input_tokens == 0
            assert log.output_tokens == 0
            assert log.cost_usd == 0.0
            assert log.status == "started"
        await engine.dispose()

    asyncio.run(_test())
