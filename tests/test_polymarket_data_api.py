"""Tests for Polymarket Data API methods."""

from unittest.mock import MagicMock, patch
import pytest
from config import PolymarketConfig


class TestPolymarketDataAPI:
    @patch("clients.polymarket_client.requests.Session")
    def test_get_leaderboard(self, mock_session_cls):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"rank": "1", "proxyWallet": "0xabc", "userName": "Top",
             "vol": 100000, "pnl": 50000, "verifiedBadge": True}
        ]
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        from clients.polymarket_client import PolymarketClient
        config = PolymarketConfig()
        client = PolymarketClient(config)
        client.session = mock_session

        leaders = client.get_leaderboard(category="OVERALL", limit=10)
        assert len(leaders) == 1
        assert leaders[0]["userName"] == "Top"
        mock_session.get.assert_called_once()

    @patch("clients.polymarket_client.requests.Session")
    def test_get_trades_with_filters(self, mock_session_cls):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [{"side": "BUY", "size": 10000}]
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        from clients.polymarket_client import PolymarketClient
        config = PolymarketConfig()
        client = PolymarketClient(config)
        client.session = mock_session

        trades = client.get_trades(
            filter_type="CASH", filter_amount=5000, limit=50)
        assert len(trades) == 1

    @patch("clients.polymarket_client.requests.Session")
    def test_get_positions(self, mock_session_cls):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"conditionId": "c1", "title": "Test", "currentValue": 5000}
        ]
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        from clients.polymarket_client import PolymarketClient
        config = PolymarketConfig()
        client = PolymarketClient(config)
        client.session = mock_session

        positions = client.get_positions(user="0xabc123")
        assert len(positions) == 1

    @patch("clients.polymarket_client.requests.Session")
    def test_get_portfolio_value(self, mock_session_cls):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": 125000.50}
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        from clients.polymarket_client import PolymarketClient
        config = PolymarketConfig()
        client = PolymarketClient(config)
        client.session = mock_session

        result = client.get_portfolio_value("0xabc")
        assert result["value"] == 125000.50
