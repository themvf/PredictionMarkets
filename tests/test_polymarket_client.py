"""Tests for Polymarket client — Gamma API request construction."""

from unittest.mock import MagicMock, patch

import pytest

from config import PolymarketConfig


class TestPolymarketClient:
    @patch("clients.polymarket_client.requests.Session")
    def test_get_gamma_markets_params(self, mock_session_cls):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "1", "question": "Test?"}]
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        from clients.polymarket_client import PolymarketClient
        config = PolymarketConfig()
        client = PolymarketClient(config)
        client.session = mock_session

        markets = client.get_gamma_markets(limit=10, offset=0)
        assert len(markets) == 1
        mock_session.get.assert_called_once()

    @patch("clients.polymarket_client.requests.Session")
    def test_get_all_active_markets_pagination(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        page1 = [{"id": str(i)} for i in range(100)]
        page2 = [{"id": str(i)} for i in range(50)]

        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = page1
        mock_resp1.status_code = 200

        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = page2
        mock_resp2.status_code = 200

        mock_session.get.side_effect = [mock_resp1, mock_resp2]

        from clients.polymarket_client import PolymarketClient
        config = PolymarketConfig()
        client = PolymarketClient(config)
        client.session = mock_session

        markets = client.get_all_active_markets(max_pages=5, page_size=100)
        assert len(markets) == 150

    def test_health_check_url(self):
        from clients.polymarket_client import PolymarketClient
        config = PolymarketConfig()
        client = PolymarketClient(config)
        assert client.gamma_url == "https://gamma-api.polymarket.com"
        assert client.clob_url == "https://clob.polymarket.com"
