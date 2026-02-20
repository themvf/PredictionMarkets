"""Tests for Kalshi API client — signing logic and request construction."""

import base64
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from config import KalshiConfig


class TestKalshiSigning:
    def test_sign_request_produces_base64(self):
        """Verify the signature is valid base64."""
        from clients.kalshi_client import KalshiClient

        config = KalshiConfig(
            api_key_id="test-key",
            private_key_path=str(Path("C:/Docs/_AI Python Projects/Kalshi/Kalshi.txt")),
        )

        try:
            client = KalshiClient(config)
        except FileNotFoundError:
            pytest.skip("Kalshi private key not available")

        sig = client._sign_request("GET", "/markets", "1234567890")
        decoded = base64.b64decode(sig)
        assert len(decoded) > 0

    def test_sign_different_inputs_differ(self):
        """Different inputs should produce different signatures."""
        from clients.kalshi_client import KalshiClient

        config = KalshiConfig(
            api_key_id="test-key",
            private_key_path=str(Path("C:/Docs/_AI Python Projects/Kalshi/Kalshi.txt")),
        )

        try:
            client = KalshiClient(config)
        except FileNotFoundError:
            pytest.skip("Kalshi private key not available")

        sig1 = client._sign_request("GET", "/markets", "1111111111")
        sig2 = client._sign_request("GET", "/markets", "2222222222")
        assert sig1 != sig2

    def test_rate_limit_delay(self):
        """Verify rate limiter is configured."""
        config = KalshiConfig(rate_limit_delay=0.06)
        assert config.rate_limit_delay == 0.06


class TestKalshiClientMethods:
    @patch("clients.kalshi_client.KalshiClient._request")
    @patch("clients.kalshi_client.KalshiClient._load_private_key")
    def test_get_markets_params(self, mock_key, mock_request):
        mock_key.return_value = MagicMock()
        mock_request.return_value = {"markets": [], "cursor": None}

        from clients.kalshi_client import KalshiClient
        config = KalshiConfig(api_key_id="test", private_key_path="dummy")
        client = KalshiClient(config)

        client.get_markets(limit=50, status="open")
        mock_request.assert_called_once_with(
            "GET", "/markets",
            params={"limit": 50, "status": "open"},
        )

    @patch("clients.kalshi_client.KalshiClient._request")
    @patch("clients.kalshi_client.KalshiClient._load_private_key")
    def test_get_all_active_markets_pagination(self, mock_key, mock_request):
        mock_key.return_value = MagicMock()
        mock_request.side_effect = [
            {"markets": [{"ticker": f"M{i}"} for i in range(200)], "cursor": "next"},
            {"markets": [{"ticker": f"M{i}"} for i in range(50)], "cursor": None},
        ]

        from clients.kalshi_client import KalshiClient
        config = KalshiConfig(api_key_id="test", private_key_path="dummy")
        client = KalshiClient(config)

        markets = client.get_all_active_markets(max_pages=5)
        assert len(markets) == 250
