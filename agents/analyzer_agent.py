"""Cross-Platform Analyzer Agent.

Compares matched market pairs, calculates price gaps, and uses GPT-4o
for qualitative analysis of significant discrepancies.

Schedule: Every 15 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import AnalysisResult


class AnalyzerAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="analyzer", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        openai_client = context.get("openai_client")

        pairs = queries.get_all_pairs()
        analyses_created = 0
        significant_gaps = 0

        for pair in pairs:
            kalshi_yes = pair.get("kalshi_yes")
            poly_yes = pair.get("poly_yes")

            if kalshi_yes is None or poly_yes is None:
                continue

            price_gap = abs(kalshi_yes - poly_yes)
            gap_direction = "kalshi_higher" if kalshi_yes > poly_yes else "poly_higher"

            # Update pair's price gap
            from db.models import MarketPair
            updated_pair = MarketPair(
                kalshi_market_id=pair["kalshi_market_id"],
                polymarket_market_id=pair["polymarket_market_id"],
                match_confidence=pair.get("match_confidence", 0),
                match_reason=pair.get("match_reason", ""),
                price_gap=price_gap,
            )
            queries.upsert_pair(updated_pair)

            # Only do LLM analysis for significant gaps (> 3 cents)
            llm_analysis = None
            risk_score = None
            if price_gap >= 0.03 and openai_client:
                significant_gaps += 1
                try:
                    analysis = self._analyze_gap(pair, price_gap, gap_direction, openai_client)
                    llm_analysis = json.dumps(analysis)
                    risk_score = analysis.get("risk_score")
                except Exception:
                    llm_analysis = None

            result = AnalysisResult(
                pair_id=pair["id"],
                kalshi_yes=kalshi_yes,
                poly_yes=poly_yes,
                price_gap=price_gap,
                gap_direction=gap_direction,
                llm_analysis=llm_analysis,
                risk_score=risk_score,
            )
            queries.insert_analysis(result)
            analyses_created += 1

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=analyses_created,
            summary=f"Analyzed {analyses_created} pairs. {significant_gaps} with significant gaps (>3c).",
            data={
                "analyses_created": analyses_created,
                "significant_gaps": significant_gaps,
            },
        )

    def _analyze_gap(self, pair: Dict[str, Any], price_gap: float,
                     gap_direction: str, openai_client: Any) -> Dict[str, Any]:
        """Send gap to GPT-4o for qualitative analysis."""
        from llm.prompts import PROMPTS

        kalshi_market = pair.get("kalshi_title", "Unknown")
        poly_market = pair.get("poly_title", "Unknown")

        prompt = PROMPTS["gap_analysis"].format(
            kalshi_title=kalshi_market,
            kalshi_yes=f"${pair.get('kalshi_yes', 0):.2f}",
            kalshi_volume=pair.get("kalshi_volume", "N/A"),
            kalshi_category=pair.get("kalshi_category", "N/A"),
            poly_title=poly_market,
            poly_yes=f"${pair.get('poly_yes', 0):.2f}",
            poly_volume=pair.get("poly_volume", "N/A"),
            poly_category=pair.get("poly_category", "N/A"),
            price_gap=f"${price_gap:.2f}",
            gap_direction=gap_direction,
        )

        return openai_client.chat(prompt, expect_json=True)
