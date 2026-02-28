"""Polymarket API client — Gamma (discovery) + CLOB (pricing) + Data API (traders).

Gamma API: https://gamma-api.polymarket.com — no auth required
  - /markets — paginated market discovery
  - /events — event-level grouping

CLOB API: https://clob.polymarket.com — no auth for read operations
  - /book — orderbook
  - /price — current midpoint price
  - /midpoint — midpoint for a token
  - /spreads — bid/ask spread

Data API: https://data-api.polymarket.com — no auth for read operations
  - /v1/leaderboard — trader rankings by PnL/volume
  - /trades — trade history (filterable by user, market, size)
  - /positions — user positions with P&L
  - /value — portfolio value
  - /holders — top holders for a market

Uses py-clob-client SDK for CLOB operations when available,
falls back to raw requests.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from config import PolymarketConfig


class PolymarketClient:
    def __init__(self, config: PolymarketConfig) -> None:
        self.config = config
        self.gamma_url = config.gamma_url
        self.clob_url = config.clob_url
        self.data_api_url = config.data_api_url
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "PredictionMarkets-Agent/1.0",
        })
        self._clob_client = None
        self._init_clob_client()

    def _init_clob_client(self) -> None:
        """Attempt to initialize py-clob-client SDK."""
        try:
            from py_clob_client.client import ClobClient
            self._clob_client = ClobClient(self.clob_url)
        except Exception:
            self._clob_client = None

    # ── Gamma API (Discovery) ────────────────────────────────

    def get_gamma_markets(self, limit: int = 100,
                          offset: int = 0,
                          active: bool = True,
                          closed: bool = False) -> List[Dict[str, Any]]:
        """Fetch markets from Gamma API with pagination."""
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }
        resp = self.session.get(
            f"{self.gamma_url}/markets",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_all_active_markets(self, max_pages: int = 10,
                                page_size: int = 100) -> List[Dict[str, Any]]:
        """Paginate through all active Gamma markets."""
        all_markets: List[Dict[str, Any]] = []
        for page in range(max_pages):
            markets = self.get_gamma_markets(
                limit=page_size,
                offset=page * page_size,
                active=True,
            )
            if not markets:
                break
            all_markets.extend(markets)
            if len(markets) < page_size:
                break
        return all_markets

    def get_gamma_events(self, limit: int = 100,
                         offset: int = 0,
                         active: bool = True) -> List[Dict[str, Any]]:
        """Fetch events from Gamma API."""
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
        }
        resp = self.session.get(
            f"{self.gamma_url}/events",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_gamma_market(self, condition_id: str) -> Dict[str, Any]:
        """Fetch a single market by condition ID from Gamma."""
        resp = self.session.get(
            f"{self.gamma_url}/markets/{condition_id}",
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── CLOB API (Pricing) ───────────────────────────────────

    def get_orderbook(self, token_id: str) -> Dict[str, Any]:
        """Fetch orderbook for a token from CLOB API."""
        if self._clob_client:
            try:
                return self._clob_client.get_order_book(token_id)
            except Exception:
                pass
        # Fallback to raw request
        resp = self.session.get(
            f"{self.clob_url}/book",
            params={"token_id": token_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_price(self, token_id: str) -> Dict[str, Any]:
        """Fetch current price for a token."""
        if self._clob_client:
            try:
                return self._clob_client.get_price(token_id)
            except Exception:
                pass
        resp = self.session.get(
            f"{self.clob_url}/price",
            params={"token_id": token_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Fetch midpoint price for a token."""
        if self._clob_client:
            try:
                mid = self._clob_client.get_midpoint(token_id)
                return float(mid) if mid else None
            except Exception:
                pass
        resp = self.session.get(
            f"{self.clob_url}/midpoint",
            params={"token_id": token_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        mid = data.get("mid")
        return float(mid) if mid else None

    def get_spread(self, token_id: str) -> Dict[str, Any]:
        """Fetch bid/ask spread for a token."""
        if self._clob_client:
            try:
                return self._clob_client.get_spread(token_id)
            except Exception:
                pass
        resp = self.session.get(
            f"{self.clob_url}/spread",
            params={"token_id": token_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_midpoints_batch(self, token_ids: List[str]) -> Dict[str, Optional[float]]:
        """Fetch midpoints for multiple tokens."""
        results = {}
        for token_id in token_ids:
            try:
                results[token_id] = self.get_midpoint(token_id)
            except Exception:
                results[token_id] = None
        return results

    def health_check(self) -> bool:
        """Test connectivity to Polymarket APIs."""
        try:
            resp = self.session.get(
                f"{self.gamma_url}/markets",
                params={"limit": 1},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── Data API (Leaderboard, Trades, Positions) ─────────

    def get_leaderboard(self, category: str = "OVERALL",
                        time_period: str = "ALL",
                        order_by: str = "PNL",
                        limit: int = 25,
                        offset: int = 0) -> List[Dict[str, Any]]:
        """Fetch trader leaderboard from Data API.

        Categories: OVERALL, POLITICS, SPORTS, CRYPTO, CULTURE,
                    MENTIONS, WEATHER, ECONOMICS, TECH, FINANCE
        Time periods: DAY, WEEK, MONTH, ALL
        Order by: PNL, VOL
        """
        params: Dict[str, Any] = {
            "category": category,
            "timePeriod": time_period,
            "orderBy": order_by,
            "limit": limit,
            "offset": offset,
        }
        resp = self.session.get(
            f"{self.data_api_url}/v1/leaderboard",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_trades(self, user: Optional[str] = None,
                   market: Optional[str] = None,
                   side: Optional[str] = None,
                   limit: int = 100,
                   offset: int = 0,
                   filter_type: Optional[str] = "CASH",
                   filter_amount: Optional[float] = None) -> List[Dict[str, Any]]:
        """Fetch trades from Data API.

        Can filter by user wallet, market condition ID, side (BUY/SELL),
        and minimum trade size.
        """
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if user:
            params["user"] = user
        if market:
            params["market"] = market
        if side:
            params["side"] = side
        if filter_type and filter_amount is not None:
            params["filterType"] = filter_type
            params["filterAmount"] = filter_amount
        resp = self.session.get(
            f"{self.data_api_url}/trades",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_positions(self, user: str,
                      market: Optional[str] = None,
                      size_threshold: float = 1.0,
                      limit: int = 100,
                      offset: int = 0,
                      sort_by: str = "CURRENT") -> List[Dict[str, Any]]:
        """Fetch user positions from Data API.

        sort_by options: TOKENS, CURRENT, INITIAL, CASHPNL,
                         PERCENTPNL, TITLE, RESOLVING, PRICE
        """
        params: Dict[str, Any] = {
            "user": user,
            "sizeThreshold": size_threshold,
            "limit": limit,
            "offset": offset,
            "sortBy": sort_by,
        }
        if market:
            params["market"] = market
        resp = self.session.get(
            f"{self.data_api_url}/positions",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_portfolio_value(self, user: str) -> Dict[str, Any]:
        """Fetch total portfolio value for a user."""
        resp = self.session.get(
            f"{self.data_api_url}/value",
            params={"user": user},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_market_holders(self, market: str,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch top holders for a specific market."""
        resp = self.session.get(
            f"{self.data_api_url}/holders",
            params={"market": market, "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
