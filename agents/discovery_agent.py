"""Market Discovery Agent.

Scans Polymarket for active events, normalizes each nested market to a
common schema (NormalizedMarket), and persists to the database using
batch writes.

Uses the /events endpoint (not /markets) because modern Polymarket
markets carry rich categorization via event-level **tags** arrays
(e.g. ["Finance", "Equities", "Earnings"]) while the market-level
`category` field is often empty.

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
from utils.categories import (
    normalize_category,
    extract_subcategory,
    category_from_tags,
)


class DiscoveryAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="discovery", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        polymarket_client = context.get("polymarket_client")

        poly_count = 0

        # ── Fetch Polymarket events (with tags + nested markets) ──
        if polymarket_client:
            try:
                raw_events = polymarket_client.get_all_active_events(max_pages=50)
                normalized: List[NormalizedMarket] = []
                for event in raw_events:
                    normalized.extend(self._normalize_event(event))
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

    def _normalize_event(self, event: Dict[str, Any]) -> List[NormalizedMarket]:
        """Convert a Polymarket event (with nested markets) to NormalizedMarkets.

        Category resolution priority:
        1. Event-level tags (most reliable for modern markets)
        2. Market-level category field
        3. Event seriesSlug
        4. Title keyword fallback
        """
        tags = event.get("tags", [])
        tag_category, tag_subcategory = category_from_tags(tags)

        event_slug = event.get("slug", "")
        event_series = event.get("seriesSlug", "")

        markets = event.get("markets", [])
        # If the event has no nested markets, treat the event itself as a market
        if not markets:
            markets = [event]

        results: List[NormalizedMarket] = []
        for raw in markets:
            nm = self._normalize_market(
                raw, event, tag_category, tag_subcategory,
                event_slug, event_series,
            )
            if nm:
                results.append(nm)
        return results

    def _normalize_market(
        self,
        raw: Dict[str, Any],
        event: Dict[str, Any],
        tag_category: str,
        tag_subcategory: str,
        event_slug: str,
        event_series: str,
    ) -> NormalizedMarket | None:
        """Convert a single Polymarket market (within an event) to NormalizedMarket."""
        clean = sanitize_market_fields(raw)

        condition_id = sanitize_text(
            raw.get("conditionId", raw.get("id", "")), max_length=100,
        )
        if not condition_id:
            return None

        title = clean.get("question", clean.get("title", ""))

        # ── Category resolution ──────────────────────────────
        # Priority: tags > market category > seriesSlug > title keywords
        if tag_category:
            category = tag_category
        else:
            raw_category = clean.get("category", "")
            if not raw_category:
                raw_category = sanitize_text(event_series or "", max_length=100)
            if not raw_category:
                raw_category = clean.get("groupItemTitle", "")
            category = normalize_category(raw_category, title)

        # ── Subcategory resolution ───────────────────────────
        # Priority: tag-derived subcategory > title keyword extraction
        if tag_subcategory:
            subcategory = tag_subcategory
        else:
            subcategory = extract_subcategory(category, title)

        # ── Prices ───────────────────────────────────────────
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

        slug = raw.get("slug", event_slug)

        return NormalizedMarket(
            platform="polymarket",
            platform_id=condition_id,
            title=title,
            description=clean.get("description", event.get("description", "")),
            category=category,
            subcategory=subcategory,
            status="active" if raw.get("active") else "closed",
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            liquidity=liquidity,
            close_time=raw.get("endDate", raw.get("end_date_iso")),
            url=f"https://polymarket.com/event/{slug}",
            raw_data=json.dumps(raw),
        )
