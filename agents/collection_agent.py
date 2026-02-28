"""Data Collection Agent.

Fetches current prices, volumes, and orderbook snapshots for all
tracked markets. Creates PriceSnapshot records.

Uses concurrent fetching (ThreadPoolExecutor) to parallelize API calls
across markets, reducing runtime from ~4 minutes to ~15-30 seconds.

Schedule: Every 5 minutes.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import NormalizedMarket, PriceSnapshot

# Max parallel API requests per platform
_MAX_WORKERS = 20


class CollectionAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="collection", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        kalshi_client = context.get("kalshi_client")
        polymarket_client = context.get("polymarket_client")

        snapshots_created = 0
        errors: List[str] = []

        # ── Collect Kalshi prices (concurrent) ─────────────────
        kalshi_markets = queries.get_markets_by_platform("kalshi")
        if kalshi_markets and kalshi_client:
            results = self._collect_batch(
                kalshi_markets, self._collect_kalshi, kalshi_client, "Kalshi",
            )
            for snapshot, error in results:
                if error:
                    errors.append(error)
                elif snapshot:
                    queries.insert_snapshot(snapshot)
                    queries.upsert_market(snapshot._market_update)
                    snapshots_created += 1

        # ── Collect Polymarket prices (concurrent) ─────────────
        poly_markets = queries.get_markets_by_platform("polymarket")
        if poly_markets and polymarket_client:
            results = self._collect_batch(
                poly_markets, self._collect_polymarket, polymarket_client, "Polymarket",
            )
            for snapshot, error in results:
                if error:
                    errors.append(error)
                elif snapshot:
                    queries.insert_snapshot(snapshot)
                    queries.upsert_market(snapshot._market_update)
                    snapshots_created += 1

        error_summary = f" ({len(errors)} errors)" if errors else ""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=snapshots_created,
            summary=f"Collected {snapshots_created} price snapshots{error_summary}.",
            data={
                "snapshots_created": snapshots_created,
                "errors": errors[:10],
            },
        )

    def _collect_batch(
        self,
        markets: List[Dict[str, Any]],
        collect_fn,
        client: Any,
        platform_label: str,
    ) -> List[Tuple[PriceSnapshot | None, str | None]]:
        """Fetch snapshots for a list of markets concurrently."""
        results: List[Tuple[PriceSnapshot | None, str | None]] = []

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            future_to_market = {
                executor.submit(collect_fn, market, client): market
                for market in markets
            }
            for future in as_completed(future_to_market):
                market = future_to_market[future]
                try:
                    snapshot = future.result()
                    results.append((snapshot, None))
                except Exception as e:
                    results.append((None, f"{platform_label} {market['platform_id']}: {e}"))

        return results

    def _collect_kalshi(self, market: Dict[str, Any],
                        client: Any) -> PriceSnapshot | None:
        """Fetch latest price data from Kalshi for a single market."""
        if not client:
            return None

        ticker = market["platform_id"]
        try:
            data = client.get_market(ticker)
            m = data.get("market", data)
        except Exception:
            m = market

        yes_price = m.get("yes_ask") or m.get("last_price") or market.get("yes_price")
        no_price = m.get("no_ask") or market.get("no_price")
        if yes_price is not None and yes_price > 1:
            yes_price = yes_price / 100.0
        if no_price is not None and no_price > 1:
            no_price = no_price / 100.0

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

        volume = m.get("volume", market.get("volume"))
        liquidity = m.get("open_interest", market.get("liquidity"))

        market_update = NormalizedMarket(
            platform="kalshi",
            platform_id=ticker,
            title=market["title"],
            description=market.get("description", ""),
            category=market.get("category", ""),
            status=market.get("status", "active"),
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            liquidity=liquidity,
            close_time=market.get("close_time"),
            url=market.get("url", ""),
        )

        snapshot = PriceSnapshot(
            market_id=market["id"],
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            open_interest=m.get("open_interest"),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
        )
        snapshot._market_update = market_update
        return snapshot

    def _collect_polymarket(self, market: Dict[str, Any],
                            client: Any) -> PriceSnapshot | None:
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
                        token_id = tokens[0]
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        yes_price = market.get("yes_price")
        no_price = market.get("no_price")
        best_bid = None
        best_ask = None
        spread = None

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

        market_update = NormalizedMarket(
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

        snapshot = PriceSnapshot(
            market_id=market["id"],
            yes_price=yes_price,
            no_price=no_price,
            volume=market.get("volume"),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
        )
        snapshot._market_update = market_update
        return snapshot
