"""Market Discovery Agent.

Scans Polymarket for active markets, normalizes them to a common schema
(NormalizedMarket), and persists to the database using batch writes.

Uses batch database operations (single connection for all markets) to
minimize round-trip overhead to Neon PostgreSQL.

Schedule: Every 30 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import NormalizedMarket
from llm.sanitize import sanitize_text, sanitize_market_fields
from utils.categories import normalize_category, extract_subcategory


class DiscoveryAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="discovery", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        polymarket_client = context.get("polymarket_client")

        poly_count = 0

        # ── Fetch Polymarket markets ─────────────────────────
        if polymarket_client:
            try:
                raw_markets = polymarket_client.get_all_active_markets(max_pages=5)
                normalized = [self._normalize_polymarket(m) for m in raw_markets]
                poly_count = queries.upsert_markets_batch(normalized)
            except Exception as e:
                context.setdefault("_errors", []).append(f"Polymarket discovery: {e}")

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=poly_count,
            summary=f"Discovered {poly_count} Polymarket markets.",
            data={"poly_count": poly_count},
        )

    def _normalize_polymarket(self, raw: Dict[str, Any]) -> NormalizedMarket:
        """Convert Polymarket Gamma API response to NormalizedMarket.

        Sanitizes all text fields at the ingestion boundary — this is the
        primary defense against prompt injection via Polymarket API data.
        """
        # Sanitize raw API data before extracting fields
        clean = sanitize_market_fields(raw)

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

        condition_id = sanitize_text(
            raw.get("conditionId", raw.get("id", "")), max_length=100,
        )

        title = clean.get("question", clean.get("title", ""))
        # Category resolution: prefer API category, then seriesSlug, then groupItemTitle
        raw_category = clean.get("category", "")
        if not raw_category:
            raw_category = sanitize_text(raw.get("seriesSlug", ""), max_length=100)
        if not raw_category:
            raw_category = clean.get("groupItemTitle", "")
        category = normalize_category(raw_category, title)
        subcategory = extract_subcategory(category, title)

        return NormalizedMarket(
            platform="polymarket",
            platform_id=condition_id,
            title=title,
            description=clean.get("description", ""),
            category=category,
            subcategory=subcategory,
            status="active" if raw.get("active") else "closed",
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            liquidity=liquidity,
            close_time=raw.get("endDate", raw.get("end_date_iso")),
            url=f"https://polymarket.com/event/{raw.get('slug', condition_id)}",
            raw_data=json.dumps(raw),
        )
