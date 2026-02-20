"""Tests for agent framework — base agent lifecycle, registry, agent execution."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agents.base import BaseAgent, AgentResult, AgentStatus
from agents.registry import AgentRegistry
from db.database import DatabaseManager
from db.queries import MarketQueries
from db.models import NormalizedMarket


class MockAgent(BaseAgent):
    """Test agent that returns a fixed result."""
    def __init__(self, name="mock", should_fail=False):
        super().__init__(name=name)
        self.should_fail = should_fail

    def execute(self, context):
        if self.should_fail:
            raise ValueError("Intentional test error")
        return AgentResult(
            agent_name=self.name,
            items_processed=42,
            summary="Mock completed",
            data={"test": True},
        )


@pytest.fixture
def context(tmp_path):
    db = DatabaseManager(tmp_path / "test.db")
    queries = MarketQueries(db)
    yield {"db": db, "queries": queries}
    try:
        with db._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass


class TestBaseAgent:
    def test_run_success(self, context):
        agent = MockAgent()
        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.items_processed == 42
        assert result.duration_seconds >= 0
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.error is None

    def test_run_error_captured(self, context):
        agent = MockAgent(should_fail=True)
        result = agent.run(context)

        assert result.status == AgentStatus.ERROR
        assert "Intentional test error" in result.error

    def test_result_stored_in_context(self, context):
        agent = MockAgent(name="test_agent")
        agent.run(context)

        assert "result_test_agent" in context
        assert context["result_test_agent"].status == AgentStatus.SUCCESS

    def test_agent_status_updates(self, context):
        agent = MockAgent()
        assert agent.status == AgentStatus.IDLE
        agent.run(context)
        assert agent.status == AgentStatus.SUCCESS


class TestAgentRegistry:
    def test_register_and_get(self):
        registry = AgentRegistry()
        agent = MockAgent(name="test")
        registry.register(agent)

        assert registry.get("test") is agent
        assert registry.get("nonexistent") is None

    def test_agent_names(self):
        registry = AgentRegistry()
        registry.register(MockAgent(name="a"))
        registry.register(MockAgent(name="b"))

        assert registry.agent_names == ["a", "b"]

    def test_run_all(self, context):
        registry = AgentRegistry()
        registry.register(MockAgent(name="first"))
        registry.register(MockAgent(name="second"))

        results = registry.run_all(context)
        assert len(results) == 2
        assert all(r.status == AgentStatus.SUCCESS for r in results)

    def test_run_one(self, context):
        registry = AgentRegistry()
        registry.register(MockAgent(name="target"))

        result = registry.run_one("target", context)
        assert result.status == AgentStatus.SUCCESS

    def test_run_one_not_found(self, context):
        registry = AgentRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.run_one("missing", context)

    def test_run_all_with_failure(self, context):
        """One failing agent shouldn't prevent others from running."""
        registry = AgentRegistry()
        registry.register(MockAgent(name="good"))
        registry.register(MockAgent(name="bad", should_fail=True))
        registry.register(MockAgent(name="also_good"))

        results = registry.run_all(context)
        assert len(results) == 3
        assert results[0].status == AgentStatus.SUCCESS
        assert results[1].status == AgentStatus.ERROR
        assert results[2].status == AgentStatus.SUCCESS


class TestAgentLogging:
    def test_agent_logs_to_db(self, context):
        agent = MockAgent(name="logged_agent")
        agent.run(context)

        logs = context["queries"].get_agent_logs(agent_name="logged_agent")
        assert len(logs) == 1
        assert logs[0]["status"] == "success"
        assert logs[0]["items_processed"] == 42
