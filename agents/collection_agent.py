"""Data Collection Agent.

Fetches current prices, volumes, and orderbook snapshots for all
tracked markets. Creates PriceSnapshot records.

Schedule: Every 5 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import PriceSnapshot


class CollectionAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="collection", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        kalshi_client = context.get("kalshi_client")
        polymarket_client = context.get("polymarket_client")

        snapshots_created = 0
        errors = []

        # ── Collect Kalshi prices ────────────────────────────
        kalshi_markets = queries.get_markets_by_platform("kalshi")
        for market in kalshi_markets:
            try:
                snapshot = self._collect_kalshi(
                    market, kalshi_client, queries,
                )
                if snapshot:
                    queries.insert_snapshot(snapshot)
                    snapshots_created += 1
            except Exception as e:
                errors.append(f"Kalshi {market['platform_id']}: {e}")

        # ── Collect Polymarket prices ────────────────────────
        poly_markets = queries.get_markets_by_platform("polymarket")
        for market in poly_markets:
            try:
                snapshot = self._collect_polymarket(
                    market, polymarket_client, queries,
                )
                if snapshot:
                    queries.insert_snapshot(snapshot)
                    snapshots_created += 1
            except Exception as e:
                errors.append(f"Polymarket {market['platform_id']}: {e}")

        error_summary = f" ({len(errors)} errors)" if errors else ""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=snapshots_created,
            summary=f"Collected {snapshots_created} price snapshots{error_summary}.",
            data={
                "snapshots_created": snapshots_created,
                "errors": errors[:10],  # Keep first 10 errors
            },
        )

    def _collect_kalshi(self, market: Dict[str, Any],
                        client: Any,
                        queries: Any) -> PriceSnapshot | None:
        """Fetch latest price data from Kalshi for a single market."""
        if not client:
            return None

        ticker = market["platform_id"]
        try:
            data = client.get_market(ticker)
            m = data.get("market", data)
        except Exception:
            # If individual market fetch fails, use stored data
            m = market

        yes_price = m.get("yes_ask") or m.get("last_price") or market.get("yes_price")
        no_price = m.get("no_ask") or market.get("no_price")
        if yes_price is not None and yes_price > 1:
            yes_price = yes_price / 100.0
        if no_price is not None and no_price > 1:
            no_price = no_price / 100.0

        # Try to get orderbook for bid/ask
        best_bid = None
        best_ask = None
        spread = None
        try:
            ob = client.get_orderbook(ticker)
            orderbook = ob.get("orderbook", ob)
            yes_bids = orderbook.get("yes", [])
            if yes_bids:
                best_bid = yes_bids[0][0] / 100.0 if yes_bids[0][0] > 1 else yes_bids[0][0]
            no_asks = orderbook.get("no", [])
            if best_bid and best_ask:
                spread = best_ask - best_bid
        except Exception:
            pass

        # Update the market's current price in the markets table
        from db.models import NormalizedMarket
        updated = NormalizedMarket(
            platform="kalshi",
            platform_id=ticker,
            title=market["title"],
            description=market.get("description", ""),
            category=market.get("category", ""),
            status=market.get("status", "active"),
            yes_price=yes_price,
            no_price=no_price,
            volume=m.get("volume", market.get("volume")),
            liquidity=m.get("open_interest", market.get("liquidity")),
            close_time=market.get("close_time"),
            url=market.get("url", ""),
        )
        queries.upsert_market(updated)

        return PriceSnapshot(
            market_id=market["id"],
            yes_price=yes_price,
            no_price=no_price,
            volume=m.get("volume", market.get("volume")),
            open_interest=m.get("open_interest"),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
        )

    def _collect_polymarket(self, market: Dict[str, Any],
                            client: Any,
                            queries: Any) -> PriceSnapshot | None:
        """Fetch latest price data from Polymarket for a single market."""
        if not client:
            return None

        condition_id = market["platform_id"]

        # Extract token IDs from raw_data if available
        token_id = None
        raw = market.get("raw_data")
        if raw:
            try:
                raw_data = json.loads(raw)
                tokens = raw_data.get("clobTokenIds")
                if tokens:
                    if isinstance(tokens, str):
                        tokens = json.loads(tokens)
                    if tokens:
                        token_id = tokens[0]  # Yes token
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        yes_price = market.get("yes_price")
        no_price = market.get("no_price")
        best_bid = None
        best_ask = None
        spread = None

        # Try CLOB API if we have a token ID
        if token_id:
            try:
                mid = client.get_midpoint(token_id)
                if mid is not None:
                    yes_price = mid
                    no_price = 1.0 - mid
            except Exception:
                pass

            try:
                ob = client.get_orderbook(token_id)
                bids = ob.get("bids", [])
                asks = ob.get("asks", [])
                if bids:
                    best_bid = float(bids[0].get("price", 0))
                if asks:
                    best_ask = float(asks[0].get("price", 0))
                if best_bid and best_ask:
                    spread = best_ask - best_bid
            except Exception:
                pass
        else:
            # Fallback: try Gamma API refresh
            try:
                data = client.get_gamma_market(condition_id)
                outcomes_prices = data.get("outcomePrices")
                if outcomes_prices:
                    if isinstance(outcomes_prices, str):
                        prices = json.loads(outcomes_prices)
                    else:
                        prices = outcomes_prices
                    if len(prices) >= 1:
                        yes_price = float(prices[0])
                    if len(prices) >= 2:
                        no_price = float(prices[1])
            except Exception:
                pass

        # Update the market's current price
        from db.models import NormalizedMarket
        updated = NormalizedMarket(
            platform="polymarket",
            platform_id=condition_id,
            title=market["title"],
            description=market.get("description", ""),
            category=market.get("category", ""),
            status=market.get("status", "active"),
            yes_price=yes_price,
            no_price=no_price,
            volume=market.get("volume"),
            liquidity=market.get("liquidity"),
            close_time=market.get("close_time"),
            url=market.get("url", ""),
        )
        queries.upsert_market(updated)

        return PriceSnapshot(
            market_id=market["id"],
            yes_price=yes_price,
            no_price=no_price,
            volume=market.get("volume"),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
        )
