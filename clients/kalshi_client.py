"""Kalshi REST API client with RSA-PSS signature authentication.

Auth flow:
1. Load RSA private key from file
2. For each request, create a timestamp + method + path signature
3. Sign with RSA-PSS (SHA-256) and send in headers

Rate limit: 0.06s delay between calls (~16 req/sec, under 20/sec limit).
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from config import KalshiConfig


class KalshiClient:
    def __init__(self, config: KalshiConfig) -> None:
        self.config = config
        self.base_url = config.base_url
        self.session = requests.Session()
        self._last_request_time = 0.0
        self._private_key = self._load_private_key()

    def _load_private_key(self) -> Any:
        """Load RSA private key from the configured file path."""
        key_path = Path(self.config.private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(f"Kalshi private key not found: {key_path}")
        key_data = key_path.read_bytes()
        return serialization.load_pem_private_key(key_data, password=None)

    def _sign_request(self, method: str, path: str, timestamp: str) -> str:
        """Create RSA-PSS signature for Kalshi API authentication.

        The signature payload is: timestamp + method + path
        """
        message = f"{timestamp}{method}{path}".encode("utf-8")
        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _rate_limit(self) -> None:
        """Enforce minimum delay between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, path: str,
                 params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an authenticated request to Kalshi API."""
        self._rate_limit()
        url = f"{self.base_url}{path}"
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        signature = self._sign_request(method.upper(), path, timestamp)

        headers = {
            "KALSHI-ACCESS-KEY": self.config.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ── Public API Methods ───────────────────────────────────

    def get_markets(self, limit: int = 200,
                    cursor: Optional[str] = None,
                    status: str = "open",
                    series_ticker: Optional[str] = None,
                    event_ticker: Optional[str] = None) -> Dict[str, Any]:
        """Fetch markets with pagination support."""
        params: Dict[str, Any] = {"limit": limit, "status": status}
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        return self._request("GET", "/markets", params=params)

    def get_all_active_markets(self, max_pages: int = 10) -> List[Dict[str, Any]]:
        """Paginate through all active markets."""
        all_markets: List[Dict[str, Any]] = []
        cursor = None
        for _ in range(max_pages):
            resp = self.get_markets(limit=200, cursor=cursor, status="open")
            markets = resp.get("markets", [])
            if not markets:
                break
            all_markets.extend(markets)
            cursor = resp.get("cursor")
            if not cursor:
                break
        return all_markets

    def get_market(self, ticker: str) -> Dict[str, Any]:
        """Fetch a single market by ticker."""
        return self._request("GET", f"/markets/{ticker}")

    def get_orderbook(self, ticker: str) -> Dict[str, Any]:
        """Fetch the orderbook for a market."""
        return self._request("GET", f"/markets/{ticker}/orderbook")

    def get_events(self, limit: int = 200,
                   cursor: Optional[str] = None,
                   status: str = "open") -> Dict[str, Any]:
        """Fetch events (groups of related markets)."""
        params: Dict[str, Any] = {"limit": limit, "status": status}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/events", params=params)

    def get_event(self, event_ticker: str) -> Dict[str, Any]:
        """Fetch a single event by ticker."""
        return self._request("GET", f"/events/{event_ticker}")

    def get_trades(self, ticker: str, limit: int = 100,
                   cursor: Optional[str] = None) -> Dict[str, Any]:
        """Fetch recent trades for a market."""
        params: Dict[str, Any] = {"ticker": ticker, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/markets/trades", params=params)

    def health_check(self) -> bool:
        """Test connectivity to the Kalshi API."""
        try:
            self._request("GET", "/exchange/status")
            return True
        except Exception:
            return False
