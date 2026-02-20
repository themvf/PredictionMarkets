"""Market Discovery Agent.

Scans both Kalshi and Polymarket for active markets, normalizes them
to a common schema (NormalizedMarket), persists to SQLite, and optionally
uses GPT-4o to match cross-platform equivalents.

Schedule: Every 30 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import NormalizedMarket, MarketPair


class DiscoveryAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="discovery", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        kalshi_client = context.get("kalshi_client")
        polymarket_client = context.get("polymarket_client")
        openai_client = context.get("openai_client")

        kalshi_count = 0
        poly_count = 0
        pairs_found = 0

        # ── Fetch Kalshi markets ─────────────────────────────
        if kalshi_client:
            try:
                raw_markets = kalshi_client.get_all_active_markets(max_pages=5)
                for m in raw_markets:
                    market = self._normalize_kalshi(m)
                    queries.upsert_market(market)
                    kalshi_count += 1
            except Exception as e:
                # Log but continue — one platform failing shouldn't block the other
                context.setdefault("_errors", []).append(f"Kalshi discovery: {e}")

        # ── Fetch Polymarket markets ─────────────────────────
        if polymarket_client:
            try:
                raw_markets = polymarket_client.get_all_active_markets(max_pages=5)
                for m in raw_markets:
                    market = self._normalize_polymarket(m)
                    queries.upsert_market(market)
                    poly_count += 1
            except Exception as e:
                context.setdefault("_errors", []).append(f"Polymarket discovery: {e}")

        # ── Cross-platform matching ──────────────────────────
        if openai_client and kalshi_count > 0 and poly_count > 0:
            try:
                pairs_found = self._match_markets(context)
            except Exception as e:
                context.setdefault("_errors", []).append(f"Market matching: {e}")

        total = kalshi_count + poly_count
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=total,
            summary=f"Discovered {kalshi_count} Kalshi + {poly_count} Polymarket markets. {pairs_found} pairs matched.",
            data={
                "kalshi_count": kalshi_count,
                "poly_count": poly_count,
                "pairs_found": pairs_found,
            },
        )

    def _normalize_kalshi(self, raw: Dict[str, Any]) -> NormalizedMarket:
        """Convert Kalshi API response to NormalizedMarket."""
        yes_price = raw.get("yes_ask") or raw.get("last_price")
        no_price = raw.get("no_ask")
        if yes_price is not None:
            yes_price = yes_price / 100.0 if yes_price > 1 else yes_price
        if no_price is not None:
            no_price = no_price / 100.0 if no_price > 1 else no_price

        return NormalizedMarket(
            platform="kalshi",
            platform_id=raw.get("ticker", ""),
            title=raw.get("title", raw.get("subtitle", "")),
            description=raw.get("rules_primary", ""),
            category=raw.get("category", raw.get("series_ticker", "")),
            status="active" if raw.get("status") == "open" else raw.get("status", ""),
            yes_price=yes_price,
            no_price=no_price,
            volume=raw.get("volume", 0),
            liquidity=raw.get("open_interest"),
            close_time=raw.get("close_time", raw.get("expiration_time")),
            url=f"https://kalshi.com/markets/{raw.get('ticker', '')}",
            raw_data=json.dumps(raw),
        )

    def _normalize_polymarket(self, raw: Dict[str, Any]) -> NormalizedMarket:
        """Convert Polymarket Gamma API response to NormalizedMarket."""
        # Polymarket prices come as strings between "0" and "1"
        yes_price = None
        no_price = None
        outcomes_prices = raw.get("outcomePrices")
        if outcomes_prices:
            if isinstance(outcomes_prices, str):
                try:
                    prices = json.loads(outcomes_prices)
                except (json.JSONDecodeError, TypeError):
                    prices = []
            else:
                prices = outcomes_prices
            if len(prices) >= 1:
                yes_price = float(prices[0])
            if len(prices) >= 2:
                no_price = float(prices[1])

        volume_str = raw.get("volume", raw.get("volumeNum", "0"))
        try:
            volume = float(volume_str)
        except (ValueError, TypeError):
            volume = 0.0

        liquidity_str = raw.get("liquidity", raw.get("liquidityNum", "0"))
        try:
            liquidity = float(liquidity_str)
        except (ValueError, TypeError):
            liquidity = 0.0

        # Build token IDs from tokens array for CLOB lookups
        tokens = raw.get("clobTokenIds")
        if tokens and isinstance(tokens, str):
            try:
                tokens = json.loads(tokens)
            except (json.JSONDecodeError, TypeError):
                tokens = []

        condition_id = raw.get("conditionId", raw.get("id", ""))

        return NormalizedMarket(
            platform="polymarket",
            platform_id=condition_id,
            title=raw.get("question", raw.get("title", "")),
            description=raw.get("description", ""),
            category=raw.get("category", raw.get("groupItemTitle", "")),
            status="active" if raw.get("active") else "closed",
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            liquidity=liquidity,
            close_time=raw.get("endDate", raw.get("end_date_iso")),
            url=f"https://polymarket.com/event/{raw.get('slug', condition_id)}",
            raw_data=json.dumps(raw),
        )

    def _match_markets(self, context: Dict[str, Any]) -> int:
        """Use GPT-4o to find matching markets across platforms."""
        queries = context["queries"]
        openai_client = context["openai_client"]

        kalshi_markets = queries.get_markets_by_platform("kalshi")
        poly_markets = queries.get_markets_by_platform("polymarket")

        if not kalshi_markets or not poly_markets:
            return 0

        # Build compact lists for LLM matching
        kalshi_list = [
            {"id": m["id"], "title": m["title"], "category": m["category"]}
            for m in kalshi_markets[:100]  # Limit to top 100 by volume
        ]
        poly_list = [
            {"id": m["id"], "title": m["title"], "category": m["category"]}
            for m in poly_markets[:100]
        ]

        from llm.prompts import PROMPTS
        prompt = PROMPTS["market_matching"].format(
            kalshi_markets=json.dumps(kalshi_list, indent=2),
            polymarket_markets=json.dumps(poly_list, indent=2),
        )

        response = openai_client.chat(prompt, expect_json=True)
        matches = response.get("matches", [])

        pairs_created = 0
        for match in matches:
            kalshi_id = match.get("kalshi_id")
            poly_id = match.get("polymarket_id")
            confidence = match.get("confidence", 0.0)
            reason = match.get("reason", "")

            if kalshi_id and poly_id and confidence >= 0.7:
                # Calculate price gap
                kalshi_m = queries.get_market_by_id(kalshi_id)
                poly_m = queries.get_market_by_id(poly_id)
                price_gap = None
                if kalshi_m and poly_m and kalshi_m.get("yes_price") and poly_m.get("yes_price"):
                    price_gap = abs(kalshi_m["yes_price"] - poly_m["yes_price"])

                pair = MarketPair(
                    kalshi_market_id=kalshi_id,
                    polymarket_market_id=poly_id,
                    match_confidence=confidence,
                    match_reason=reason,
                    price_gap=price_gap,
                )
                queries.upsert_pair(pair)
                pairs_created += 1

        return pairs_created
