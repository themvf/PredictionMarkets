"""Tests for the whale monitoring agent."""

from unittest.mock import MagicMock
import pytest
from db.database import DatabaseManager
from db.queries import MarketQueries
from agents.whale_agent import WhaleAgent


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


class TestWhaleAgent:
    def test_skips_without_client(self, context):
        agent = WhaleAgent()
        result = agent.run(context)
        assert "Skipped" in result.summary

    def test_processes_trades(self, context):
        mock_client = MagicMock()
        mock_client.get_trades.return_value = [
            {
                "proxyWallet": "0xabc",
                "transactionHash": "0xtx1",
                "conditionId": "cond1",
                "title": "Test Market",
                "side": "BUY",
                "size": 10000,
                "price": 0.65,
                "outcome": "Yes",
                "outcomeIndex": 0,
                "timestamp": 1700000000,
                "eventSlug": "test",
                "pseudonym": "TestWhale",
                "profileImage": "",
            },
        ]
        context["polymarket_client"] = mock_client
        agent = WhaleAgent()
        result = agent.run(context)
        assert result.data.get("trades_stored", 0) >= 1

    def test_handles_empty_trades(self, context):
        mock_client = MagicMock()
        mock_client.get_trades.return_value = []
        context["polymarket_client"] = mock_client
        agent = WhaleAgent()
        result = agent.run(context)
        assert result.data.get("trades_stored") == 0

    def test_handles_api_error(self, context):
        mock_client = MagicMock()
        mock_client.get_trades.side_effect = Exception("API timeout")
        context["polymarket_client"] = mock_client
        agent = WhaleAgent()
        result = agent.run(context)
        assert len(result.data.get("errors", [])) > 0
